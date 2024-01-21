import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_operations import get_bot_token, insert_response_message, mark_message_status
from app.controllers.ai_communication import get_chat_completion
from app.controllers.telegram_integration import send_telegram_message
from app.models.message import tbl_msg
from sqlalchemy.future import select
import asyncio

logger = logging.getLogger(__name__)

async def process_queue(chat_id: int, db: AsyncSession):
    try:
        timestamp = datetime.now()
        await asyncio.sleep(3)
        logger.info(f"Processing queue for chat_id {chat_id} as of {timestamp}")

        stmt = select(tbl_msg).where(tbl_msg.chat_id == chat_id, tbl_msg.is_processed == 'N').order_by(tbl_msg.message_date.desc())
        async with db:
            result = await db.execute(stmt)
            unprocessed_messages = result.scalars().all()

        if unprocessed_messages:
            if unprocessed_messages[0].message_date <= timestamp:
                for message in unprocessed_messages:
                    await process_message(message, db, chat_id)
            else:
                logger.info(f"Skipping processing: Newest message for chat_id {chat_id} is newer than the timestamp.")
        else:
            logger.info(f"No unprocessed messages found for chat_id {chat_id}")

    except Exception as e:
        logger.error(f'Error processing queue: {e}')
        await db.rollback()
    finally:
        await db.close()


async def process_message(message, db, chat_id):
    await mark_message_status(db, message.pk_messages, 'P')
    response_text = await get_chat_completion(chat_id, message.bot_id, db)

    if response_text:
        bot_token = await get_bot_token(message.bot_id, db)
        await send_telegram_message(chat_id, response_text, bot_token)
        await insert_response_message(db, 'TELEGRAM', message.bot_id, chat_id, response_text, 'TEXT', 'ASSISTANT', 'Y')

    await mark_message_status(db, message.pk_messages, 'Y')
    logger.info(f"Message {message.pk_messages} processed for chat_id {chat_id}")

