# ./app/controllers/message_processing.py
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_operations import (
   update_user_credits,
   get_bot_config,
   add_messages,
   update_message,
   check_if_chat_is_awaiting,
   manage_awaiting_status,
)
from app.controllers.ai_communication import get_chat_completion, generate_photo_reaction
from app.controllers.telegram_integration import (
   send_typing_action,
   update_telegram_message,
   send_telegram_message,
   send_audio_message,
   send_voice_note,
   send_photo_message,
)
from app.models.message import tbl_msg
from app.models import message  # Ensure this is imported
from sqlalchemy.future import select
from app.schemas import TextMessage
from app.utils.generate_audio import (
   generate_audio_from_text,
   generate_audio_with_monsterapi,
)
from app.utils.generate_photo import generate_photo_from_text
from app.utils.caption_photo import get_caption_for_local_photo

from app.config import CREDIT_COST_PHOTO, CREDIT_COST_AUDIO, CREDIT_COST_TEXT
from app.utils.error_handler import send_error_notification
import asyncio
import regex as re

logger = logging.getLogger(__name__)

async def process_queue(
   chat_id: int,
   bot_id: int,
   user_id: int,
   message_pk: int,
   ai_placeholder_pk: int,
   db: AsyncSession,
):
   try:
       timestamp = datetime.utcnow()
       await asyncio.sleep(3)
       logger.info(f"Processing queue for chat_id {chat_id} as of {timestamp}")

       stmt = (
           select(tbl_msg)
           .where(tbl_msg.chat_id == chat_id, tbl_msg.is_processed == "N")
           .order_by(tbl_msg.message_date.desc())
       )
       async with db:
           result = await db.execute(stmt)
           unprocessed_messages = result.scalars().all()

       logger.debug(f"Unprocessed messages: {unprocessed_messages}")

       if unprocessed_messages:
           logger.info(
               f"Comparing message_date {unprocessed_messages[0].message_date} and timestamp {timestamp}"
           )

           if unprocessed_messages[0].message_date <= timestamp:
               await process_message(
                   unprocessed_messages, db, chat_id, bot_id, user_id, ai_placeholder_pk
               )
           else:
               logger.info(
                   f"Skipping processing: New message for chat_id {chat_id} arrived during wait."
               )

   except Exception as e:
       logger.error(f"Error processing queue: {e}")
       await db.rollback()
       await send_error_notification(
           chat_id,
           await get_bot_config(db, return_type="token", bot_id=bot_id),
           "Error: e001",
       )
   finally:
       await db.close()

async def process_message(
   messages, db, chat_id, bot_id, user_id, ai_placeholder_pk: int
):
   logger.debug(f"Messages to process: {messages}")

   bot_token = await get_bot_config(db, return_type="token", bot_id=messages[0].bot_id)

   logger.debug(f"messages[0].bot_id new catch: {messages[0].bot_id}")
   logger.debug(f"bot_token new catch: {bot_token}")

   await send_typing_action(chat_id, bot_token)

   for message in messages:
       await update_message(db, message_pk=message.pk_messages, new_status="P")

   response_text = None
   
   if await check_if_chat_is_awaiting(db=db, chat_id=chat_id, awaiting_type="AUDIO"):
      success, generating_message_id = await send_telegram_message(
         chat_id=chat_id, text="Generating audio, please wait.", bot_token=bot_token
      )

      if success:
         logger.debug(f"user is awaiting audio generation")
         await manage_awaiting_status(
               db, chat_id=chat_id, channel="TELEGRAM", action="REMOVE"
         )

         response_text = await get_chat_completion(chat_id, messages[0].bot_id, db)
         
         logger.debug(f"Chat completion response: {response_text}")

         audio_generation_task = asyncio.create_task(
               generate_audio_with_monsterapi(text=response_text)
         )

         try:
               while not audio_generation_task.done():
                  for i in range(4):
                     if audio_generation_task.done():
                           break
                     new_text = f"Generating audio, please wait{'.' * (i % 4)}"
                     await update_telegram_message(
                           chat_id, generating_message_id, new_text, bot_token
                     )
                     await asyncio.sleep(1)
         except asyncio.CancelledError:
               pass

         audio_file_path = await audio_generation_task

         if audio_file_path:
               await send_voice_note(
                  chat_id=chat_id, audio_file_path=audio_file_path, bot_token=bot_token
               )

               user_credit_info = {
                  "channel": "TELEGRAM",
                  "pk_bot": messages[0].bot_id,
                  "user_id": user_id,
                  "chat_id": chat_id,
                  "credits": CREDIT_COST_AUDIO,
                  "transaction_type": "AUDIO_GEN",
                  "transaction_date": datetime.utcnow(),
                  "pk_payment": None,
               }

               await update_user_credits(db, user_credit_info)

               await update_telegram_message(
                  chat_id, generating_message_id, "Audio generated successfully.", bot_token
               )
         else:
               final_message = "Sorry, I couldn't generate the audio. Please try again."
               await update_telegram_message(
                  chat_id, generating_message_id, final_message, bot_token
               )
               logger.error("Failed to generate audio")

   elif await check_if_chat_is_awaiting(db=db, chat_id=chat_id, awaiting_type="PHOTO"):
      success, generating_message_id = await send_telegram_message(
         chat_id=chat_id, text="Selecting exclusive photo, please wait.", bot_token=bot_token
      )

      if success:
         logger.debug("User is awaiting photo generation")
         await manage_awaiting_status(
               db, chat_id=chat_id, channel="TELEGRAM", action="REMOVE"
         )
         photo_generation_task = asyncio.create_task(
               generate_photo_from_text(text=messages[0].content_text)
         )

         try:
               while not photo_generation_task.done():
                  for i in range(4):
                     if photo_generation_task.done():
                           break
                     new_text = f"Selecting exclusive photo, please wait{'.' * (i % 4)}"
                     await update_telegram_message(
                           chat_id, generating_message_id, new_text, bot_token
                     )
                     await asyncio.sleep(1)
         except asyncio.CancelledError:
               pass

         photo_temp_path = await photo_generation_task

         if photo_temp_path:
            
            caption = await get_caption_for_local_photo(photo_file_path=photo_temp_path)
            response_text = await generate_photo_reaction(photo_caption=caption, file_name=photo_temp_path, bot_id=messages[0].bot_id, db=db)

            await send_photo_message(
               chat_id=chat_id, photo_temp_path=photo_temp_path, bot_token=bot_token, caption=response_text
            )

            user_credit_info = {
               "channel": "TELEGRAM",
               "pk_bot": messages[0].bot_id,
               "user_id": user_id,
               "chat_id": chat_id,
               "credits": CREDIT_COST_PHOTO,
               "transaction_type": "PHOTO_GEN",
               "transaction_date": datetime.utcnow(),
               "pk_payment": None,
            }

            await update_user_credits(db, user_credit_info)

            await update_telegram_message(
               chat_id, generating_message_id, "Photo selected successfully.", bot_token
            )
         else:
               final_message = "Sorry, I couldn't generate a photo from the description provided. Please try again."
               await update_telegram_message(
                  chat_id, generating_message_id, final_message, bot_token
               )
               logger.error("Failed to generate photo")

   else:


      response_text = await get_chat_completion(chat_id, messages[0].bot_id, db)
      
      logger.debug(f"Chat completion response: {response_text}")


      humanized_response = humanize_response(response_text)

      for chunk in humanized_response:
         await send_telegram_message(chat_id, chunk, bot_token)

   await update_message(db, message_pk=ai_placeholder_pk, new_content=response_text)
   await update_message(db, message_pk=ai_placeholder_pk, new_status="Y")

   for message in messages:
      await update_message(db, message_pk=message.pk_messages, new_status="Y")

   user_credit_info = {
      "channel": "TELEGRAM",
      "pk_bot": messages[0].bot_id,
      "user_id": user_id,
      "chat_id": chat_id,
      "credits": CREDIT_COST_TEXT,
      "transaction_type": "TEXT_GEN",
      "transaction_date": datetime.utcnow(),
      "pk_payment": None,
   }

   await update_user_credits(db, user_credit_info)
   

   logger.info(f"{len(messages)} messages processed for chat_id {chat_id}")

def humanize_response(paragraph):

   paragraph = paragraph.replace("¡", "").replace("¿", "")
   pattern = r"(?<=[.!?]) +"

   records = re.split(pattern, paragraph)

   records = [rec for rec in records if rec.strip()]

   return records