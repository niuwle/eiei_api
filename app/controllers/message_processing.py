# ./app/controllers/message_processing.py
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_operations import get_bot_short_name_by_id, update_user_credits, get_bot_token, add_messages, mark_message_status, update_message_content, check_if_chat_is_awaiting, clear_awaiting_status
from app.controllers.ai_communication import get_chat_completion
from app.controllers.telegram_integration import send_typing_action, update_telegram_message, send_telegram_message, send_audio_message, send_voice_note, send_photo_message
from app.models.message import tbl_msg
from app.models import message  # Ensure this is imported
from sqlalchemy.future import select
from app.schemas import TextMessage
from app.utils.generate_audio import generate_audio_from_text, generate_audio_with_monsterapi
from app.utils.generate_photo import generate_photo_from_text
from app.config import CREDIT_COST_PHOTO, CREDIT_COST_AUDIO, CREDIT_COST_TEXT
from app.utils.error_handler import send_error_notification
import asyncio
import regex as re


from collections import deque
from math import ceil

logger = logging.getLogger(__name__)

async def process_queue(chat_id: int, bot_id: int, user_id: int,  message_pk: int, ai_placeholder_pk: int,  db: AsyncSession):
    try:
        timestamp = datetime.now()
        await asyncio.sleep(3)
        logger.info(f"Processing queue for chat_id {chat_id} as of {timestamp}")

        stmt = select(tbl_msg).where(tbl_msg.chat_id == chat_id, tbl_msg.is_processed == 'N').order_by(tbl_msg.message_date.desc())
        async with db:
            result = await db.execute(stmt)
            unprocessed_messages = result.scalars().all()

        logger.debug(f"Unprocessed messages: {unprocessed_messages}") # Debug statement

        if unprocessed_messages:
            logger.info(f"Comparing message_date {unprocessed_messages[0].message_date} and timestamp {timestamp}")

            if unprocessed_messages[0].message_date <= timestamp:
                await process_message(unprocessed_messages, db, chat_id, bot_id, user_id, ai_placeholder_pk)
            else:
                # Skip processing as a new message arrived during the wait
                logger.info(f"Skipping processing: New message for chat_id {chat_id} arrived during wait.")
            
            
    except Exception as e:
        logger.error(f'Error processing queue: {e}')
        await db.rollback()
        await send_error_notification(chat_id, await get_bot_short_name_by_id(bot_id, db), 'Error: e001')
    finally:
        await db.close()

async def process_message(messages, db, chat_id, bot_id, user_id, ai_placeholder_pk: int):
    logger.debug(f"Messages to process: {messages}")  # Debug statement
    
    bot_token = await get_bot_token(messages[0].bot_id, db)

    await send_typing_action(chat_id, bot_token)

    # Mark all messages as processed once
    for message in messages:
        await mark_message_status(db, message.pk_messages, 'P')

    response_text = None
    retries = 3  # Maximum number of retries

    for attempt in range(retries + 1):  # Attempt up to 3 retries
        try:
            response_text = await asyncio.wait_for(get_chat_completion(chat_id, messages[0].bot_id, db), timeout=10)
            if response_text:
                break  # Break the loop if response_text is not empty
        except asyncio.TimeoutError:
            logger.error(f"get_chat_completion timed out for chat_id {chat_id}, attempt {attempt + 1}")

        if attempt < retries:  # Wait before retrying, unless it's the last attempt
            await asyncio.sleep(2)  # Wait for 2 seconds before retrying

    # Check if response_text is still None after retries
    if not response_text:
        logger.error(f"Failed to get chat completion response after {retries} retries for chat_id {chat_id}")
        await send_error_notification(chat_id, await get_bot_short_name_by_id(bot_id, db), 'Error: e002')
    else:
        logger.debug(f"Chat completion response: {response_text}")  # Debug statement
     

    if response_text:


        logger.debug(f"chat_id1234: {chat_id}") # Debug statement
        # Check if the user is awaiting audio generation
        if await check_if_chat_is_awaiting(db=db, chat_id=chat_id, awaiting_type="AUDIO"):
            # Send "Generating" message and capture its ID
            success, generating_message_id = await send_telegram_message(chat_id=chat_id, text="Generating audio, please wait.", bot_token=bot_token)
            
            if success:
                logger.debug(f"user is awaiting audio generation")  # Debug statement
                # Clear the awaiting status, as we start processing
                await clear_awaiting_status(db=db, chat_id=chat_id)

                # Start audio generation in a background task
                audio_generation_task = asyncio.create_task(
                    generate_audio_with_monsterapi(text=response_text)
                )

                # Simulate "animation" by updating the message periodically
                try:
                    while not audio_generation_task.done():
                        for i in range(4):
                            if audio_generation_task.done():
                                break  # Exit if audio generation completes
                            new_text = f"Generating audio, please wait{'.' * (i % 4)}"
                            await update_telegram_message(chat_id, generating_message_id, new_text, bot_token)
                            await asyncio.sleep(1)  # Short delay before the next update
                except asyncio.CancelledError:
                    # Handle the case where the task might be cancelled
                    pass

                # Retrieve the result of audio generation
                audio_file_path = await audio_generation_task
                
                if audio_file_path:
                    # Send the audio file to the user
                    await send_voice_note(chat_id=chat_id, audio_file_path=audio_file_path, bot_token=bot_token)

                    # Prepare the user_credit_info dictionary with necessary details
                    user_credit_info = {
                        "channel": "TELEGRAM",
                        "pk_bot": messages[0].bot_id,
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "credits": CREDIT_COST_AUDIO,
                        "transaction_type": "AUDIO_GEN",  
                        "transaction_date": datetime.utcnow(),
                        "pk_payment": None
                    }

                    # Call update_user_credits to apply the credit change
                    await update_user_credits(db, user_credit_info)
                    
                    # Update to inform the user that the audio was generated successfully
                    await update_telegram_message(chat_id, generating_message_id, "Audio generated successfully.", bot_token)
                else:
                    # If audio generation failed, inform the user
                    final_message = "Sorry, I couldn't generate the audio. Please try again."
                    await update_telegram_message(chat_id, generating_message_id, final_message, bot_token)
                    logger.error("Failed to generate audio")


        # Check if the user is awaiting photo generation
        elif await check_if_chat_is_awaiting(db=db, chat_id=chat_id, awaiting_type="PHOTO"):
            # Send "Generating" message and capture its ID
            success, generating_message_id = await send_telegram_message(chat_id=chat_id, text="Selecting exclusive photo, please wait.", bot_token=bot_token)
            
            if success:
                logger.debug("User is awaiting photo generation")
                # Clear the awaiting status for photo
                await clear_awaiting_status(db=db, chat_id=chat_id)
                # Start photo generation in a background task
                photo_generation_task = asyncio.create_task(
                    generate_photo_from_text(text=messages[0].content_text)
                )

                # Simulate "animation" by updating the message periodically
                try:
                    while not photo_generation_task.done():
                        for i in range(4):
                            if photo_generation_task.done():
                                break  # Exit if audio generation completes
                            new_text = f"Selecting exclusive photo, please wait{'.' * (i % 4)}"
                            await update_telegram_message(chat_id, generating_message_id, new_text, bot_token)
                            await asyncio.sleep(1)  # Short delay before the next update
                except asyncio.CancelledError:
                    # Handle the case where the task might be cancelled
                    pass

                # Retrieve the result of photo generation
                photo_temp_path = await photo_generation_task
                    
                if photo_temp_path:
                    # Send the generated photo URL to the user
                    await send_photo_message(chat_id=chat_id, photo_temp_path=photo_temp_path, bot_token=bot_token)

                    # Prepare the user_credit_info dictionary with necessary details
                    user_credit_info = {
                        "channel": "TELEGRAM",
                        "pk_bot": messages[0].bot_id,
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "credits": CREDIT_COST_PHOTO,
                        "transaction_type": "PHOTO_GEN",  
                        "transaction_date": datetime.utcnow(),
                        "pk_payment": None
                    }

                    # Call update_user_credits to apply the credit change
                    await update_user_credits(db, user_credit_info)
                    
                    # Update to inform the user that the audio was generated successfully
                    await update_telegram_message(chat_id, generating_message_id, "Photo selected successfully.", bot_token)
                else:
                    # If audio generation failed, inform the user
                    final_message = "Sorry, I couldn't generate a photo from the description provided. Please try again."
                    await update_telegram_message(chat_id, generating_message_id, final_message, bot_token)
                    logger.error("Failed to generate photo")


        else:

                
            # Apply humanization to the response text
            humanized_response = humanize_response(response_text)
            

            # Loop through each chunk and send it as a separate message
            for chunk in humanized_response:
                await send_telegram_message(chat_id, chunk, bot_token)


        # Use the updated add_message function to save the response
        # await add_message(db, response_message_data, type='TEXT', is_processed='Y', role='ASSISTANT')
        await update_message_content(db, ai_placeholder_pk, response_text)
        await mark_message_status(db, ai_placeholder_pk, 'Y')

        # Mark all messages as processed again
        for message in messages:
            await mark_message_status(db, message.pk_messages, 'Y')

        # Prepare the user_credit_info dictionary with necessary details
        user_credit_info = {
            "channel": "TELEGRAM",
            "pk_bot": messages[0].bot_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "credits": CREDIT_COST_TEXT,
            "transaction_type": "TEXT_GEN",  
            "transaction_date": datetime.utcnow(),
            "pk_payment": None
        }

        # Call update_user_credits to apply the credit change
        await update_user_credits(db, user_credit_info)
    else:

        # Response was not getted so we mark for reprocesing later
        for message in messages:
            await mark_message_status(db, message.pk_messages, 'N')

    # Log the count of records processed
    logger.info(f"{len(messages)} messages processed for chat_id {chat_id}") 
    

def humanize_response(paragraph):

    paragraph = paragraph.replace('¡', '').replace('¿', '')
    # Define a pattern to match a period, question mark, or exclamation mark
    pattern = r'(?<=[.!?]) +'

    # Use regex to split the paragraph into records based on the defined pattern
    records = re.split(pattern, paragraph)

    # Filter out empty strings
    records = [rec for rec in records if rec.strip()]

    return records

