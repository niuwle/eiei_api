# ./app/controllers/message_processing.py
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import asyncio
import regex as re
from app.database_operations import (get_bot_token, mark_message_status, update_message_content, 
                                     check_if_chat_is_awaiting, clear_awaiting_status)
from app.controllers.ai_communication import get_chat_completion
from app.controllers.telegram_integration import (send_telegram_message, send_voice_note, send_photo_message)
from app.utils.generate_audio import generate_audio_with_monsterapi
from app.utils.generate_photo import generate_photo_from_text
from app.models.message import tbl_msg

logger = logging.getLogger(__name__)

async def process_queue(chat_id: int, message_pk: int, ai_placeholder_pk: int, db: AsyncSession):
    logger.debug(f"Starting to process queue for chat_id: {chat_id}")
    try:
        await asyncio.sleep(3)  # Simulated delay
        stmt = select(tbl_msg).where(tbl_msg.chat_id == chat_id, tbl_msg.is_processed == 'N').order_by(tbl_msg.message_date.desc())
        async with db:
            result = await db.execute(stmt)
            messages = result.scalars().all()

        if messages and messages[0].message_date <= datetime.now():
            logger.debug(f"Found unprocessed messages for chat_id: {chat_id}, proceeding with processing")
            await process_message(messages, db, chat_id, ai_placeholder_pk)
        else:
            logger.debug(f"No unprocessed messages need immediate attention for chat_id: {chat_id}")
    except Exception as e:
        logger.error(f'Error processing queue for chat_id {chat_id}: {e}')
        await db.rollback()
    finally:
        await db.close()

async def process_message(messages, db, chat_id, ai_placeholder_pk: int):
    logger.debug(f"Processing messages for chat_id: {chat_id}")
    for message in messages:
        await mark_message_status(db, message.pk_messages, 'P')

    try:
        response_text = await asyncio.wait_for(get_chat_completion(chat_id, messages[0].bot_id, db), timeout=10)
        bot_token = await get_bot_token(messages[0].bot_id, db)
        if response_text:
            logger.debug(f"Received chat completion response for chat_id: {chat_id}")
            if await check_if_chat_is_awaiting(db=db, chat_id=chat_id, awaiting_type="AUDIO"):
                logger.debug(f"Chat is awaiting audio generation for chat_id: {chat_id}")
                success, generating_message_id = await send_telegram_message(chat_id, "Generating audio, please wait.", bot_token)
                if success:
                    audio_file_path = await generate_audio_with_monsterapi(response_text)
                    final_message = "Audio generated successfully." if audio_file_path else "Sorry, I couldn't generate the audio. Please try again."
                    await send_telegram_message(chat_id, final_message, bot_token)
            elif await check_if_chat_is_awaiting(db, chat_id, "PHOTO"):
                logger.debug(f"Chat is awaiting photo generation for chat_id: {chat_id}")
                photo_url = await generate_photo_from_text(response_text, db)
                final_message = photo_url or "Sorry, I couldn't generate a photo. Please try again."
                await send_telegram_message(chat_id, final_message, bot_token)
            else:
                for chunk in humanize_response(response_text):
                    await send_telegram_message(chat_id, chunk, bot_token)

            await update_message_content(db, ai_placeholder_pk, response_text)
            await mark_message_status(db, ai_placeholder_pk, 'Y')
        else:
            logger.debug(f"No response text available for processing for chat_id: {chat_id}")
            for message in messages:
                await mark_message_status(db, message.pk_messages, 'N')
        logger.info(f"Completed processing messages for chat_id: {chat_id}")
    except asyncio.TimeoutError:
        logger.error(f"Timeout during chat completion for chat_id: {chat_id}")

def humanize_response(paragraph):
    pattern = r'(?<=[.!?]) +'
    records = [rec for rec in re.split(pattern, paragraph.replace('¡', '').replace('¿', '')) if rec.strip()]
    logger.debug(f"Humanized response: {records}")
    return records
