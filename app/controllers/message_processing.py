# ./app/controllers/message_processing.py
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_operations import get_bot_token, add_messages, mark_message_status, update_message_content, check_if_chat_is_awaiting, clear_awaiting_status
from app.controllers.ai_communication import get_chat_completion
from app.controllers.telegram_integration import send_telegram_message, send_audio_message, send_voice_note
from app.models.message import tbl_msg
from app.models import message  # Ensure this is imported
from sqlalchemy.future import select
from app.schemas import TextMessage
from app.utils.generate_audio import generate_audio_from_text, generate_audio_with_monsterapi
import asyncio
import regex as re

from collections import deque
from math import ceil

logger = logging.getLogger(__name__)

async def process_queue(chat_id: int, message_pk: int, ai_placeholder_pk: int,  db: AsyncSession):
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
                await process_message(unprocessed_messages, db, chat_id, ai_placeholder_pk)
            else:
                # Skip processing as a new message arrived during the wait
                logger.info(f"Skipping processing: New message for chat_id {chat_id} arrived during wait.")
            
            
    except Exception as e:
        logger.error(f'Error processing queue: {e}')
        await db.rollback()
    finally:
        await db.close()


async def process_message(messages, db, chat_id, ai_placeholder_pk: int):
    logger.debug(f"Messages to process: {messages}") # Debug statement

    # Mark all messages as processed once
    for message in messages:
        await mark_message_status(db, message.pk_messages, 'P')

    # Get chat completion only once
    try:
        response_text = await asyncio.wait_for(get_chat_completion(chat_id, messages[0].bot_id, db), timeout=10)
    except asyncio.TimeoutError:
        logger.error(f"get_chat_completion timed out for chat_id {chat_id}")
        response_text = None
        
    logger.debug(f"Chat completion response: {response_text}") # Debug statement

    if response_text:

        logger.debug(f"chat_id1234: {chat_id}") # Debug statement
                # Check if the user is awaiting audio generation
        if await check_if_chat_is_awaiting(db=db, chat_id=chat_id, awaiting_type="AUDIO"):
            logger.debug(f"user is awaiting audio generation") # Debug statement
            # Generate audio from the response text
            audio_file_path = await generate_audio_with_monsterapi(text=response_text)
            if audio_file_path:
                # Send the audio file to the user
                await send_voice_note(chat_id=chat_id, audio_file_path=audio_file_path, bot_token=await get_bot_token(messages[0].bot_id, db))
                # Clear the awaiting status
                await clear_awaiting_status(db=db, chat_id=chat_id)
            else:
                logger.error("Failed to generate audio")
        else:
                
            # Apply humanization to the response text
            humanized_response = humanize_response(response_text)
            bot_token = await get_bot_token(messages[0].bot_id, db)

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

