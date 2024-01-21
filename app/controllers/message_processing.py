import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_operations import get_bot_token, insert_response_message, mark_messages_processed
from app.controllers.ai_communication import get_chat_completion
from app.controllers.telegram_integration import send_telegram_message
from app.models.message import tbl_msg
from sqlalchemy.future import select
import asyncio

# Create a logger
logger = logging.getLogger(__name__)

async def process_queue(chat_id: int, db: AsyncSession):
    try:
        # Grab the current timestamp
        timestamp = datetime.now()
        logger.info(f"Current timestamp: {timestamp}")

        # Wait for 3 seconds
        await asyncio.sleep(3)
        logger.info("Waited for 3 seconds")

        # Grab all unprocessed messages from the user
        stmt = select(tbl_msg).where(
            tbl_msg.chat_id == chat_id,
            tbl_msg.is_processed == 'N'
        ).order_by(tbl_msg.message_date.desc())

        async with db:
            result = await db.execute(stmt)
            unprocessed_messages = result.scalars().all()
            logger.info(f"Retrieved {len(unprocessed_messages)} unprocessed messages")

        # Check if the latest message is older than the timestamp grabbed before
        if unprocessed_messages:
            latest_message_timestamp = unprocessed_messages[0].message_date
            if latest_message_timestamp <= timestamp:
                for message in unprocessed_messages:
                    # Mark the message as 'pending'
                    message.is_processed = 'P'
                    await db.commit()
                    logger.info(f"Marked message as pending: {message.pk_messages}")

                    # Call the AI completion function
                    bot_id = message.bot_id
                    bot_token = await get_bot_token(bot_id, db)
                    response_text = await get_chat_completion(chat_id, bot_id, db)
                    logger.info(f"AI completion function returned: {response_text}")

                    # Send the response back to the user via Telegram
                    if response_text:
                        telegram_response = await send_telegram_message(chat_id, response_text, bot_token)
                        logger.info(f'Response from Telegram: {telegram_response}')
                        await insert_response_message(db, 'TELEGRAM', bot_id, chat_id, response_text, 'TEXT', 'ASSISTANT', 'Y')

                    # Mark the message as processed
                    message.is_processed = 'Y'
                    await db.commit()
                    logger.info(f"Marked message as processed: {message.pk_messages}")
            else:
                logger.info(f"Latest message found for chat_id {chat_id} is newer than the timestamp, skipping processing.")

    except Exception as e:
        logger.error(f'Error in process_queue: {str(e)}')
        await db.rollback()
        raise
    finally:
        await db.close()
        logger.info("Queue processing completed.")
