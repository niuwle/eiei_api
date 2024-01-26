# app/routers/database_operations.py
from sqlalchemy.orm import Session
from app.models.message import tbl_msg
from app.models.telegram_config import TelegramConfig
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import TextMessage
import logging

async def get_bot_token(bot_id: int, db: AsyncSession) -> str:
    try:
        result = await db.execute(select(TelegramConfig).filter(TelegramConfig.pk_bot == bot_id))
        bot_config = result.scalar_one_or_none()
        return bot_config.bot_token if bot_config else ''
    except SQLAlchemyError as e:
        logging.error(f"Database error in get_bot_token: {str(e)}")
        return ''

async def get_bot_id_by_short_name(bot_short_name: str, db: AsyncSession) -> int:
    try:
        result = await db.execute(select(TelegramConfig.pk_bot).filter(TelegramConfig.bot_short_name == bot_short_name))
        bot_id = result.scalar_one_or_none()
        if bot_id is not None:
            return bot_id
        else:
            logger.warning(f"No bot found with short name {bot_short_name}")
            raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_bot_id_by_short_name: {str(e)}")
        raise

async def insert_response_message(db: AsyncSession, channel: str, bot_id: int, chat_id: int, content_text: str, type: str, role: str, is_processed: str):
    new_message = tbl_msg(
        channel=channel,
        bot_id=bot_id,
        chat_id=chat_id,
        type=type,
        role=role,
        content_text=content_text,
        message_date=datetime.now(),
        is_processed=is_processed
    )
    db.add(new_message)
    await db.commit()

async def add_message(db: AsyncSession, message_data: TextMessage) -> tbl_msg:
    db_message = tbl_msg(
        chat_id=message_data.chat_id,
        user_id=message_data.user_id,
        bot_id=message_data.bot_id,
        content_text=message_data.message_text,  
        message_id=message_data.message_id,
        channel=message_data.channel,
        update_id=message_data.update_id,
        message_date=datetime.now(),
        type='TEXT',
        is_processed='N',
        role='USER'
    )
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    return db_message

async def mark_message_status(db: AsyncSession, message_pk: int, new_status: str):
    try:
        # Retrieve the message by its primary key
        result = await db.execute(select(tbl_msg).filter(tbl_msg.pk_messages == message_pk))
        message = result.scalar_one_or_none()

        # Check if the message exists
        if message:
            # Update the is_processed status of the message
            message.is_processed = new_status
            await db.commit()
            logging.info(f"Message with pk {message_pk} marked as {new_status}")
        else:
            logging.warning(f"No message found with pk {message_pk}")

    except SQLAlchemyError as e:
        logging.error(f"Database error in mark_message_status: {str(e)}")
        raise