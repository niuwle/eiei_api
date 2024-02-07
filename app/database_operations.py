from sqlalchemy.orm import Session
from app.models.message import tbl_msg
from app.models.telegram_config import TelegramConfig
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import TextMessage
from typing import List, Union
import logging

logger = logging.getLogger(__name__)

async def get_bot_token(bot_id: int, db: AsyncSession) -> str:
    try:
        query = select(TelegramConfig.bot_token).where(TelegramConfig.pk_bot == bot_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_bot_token: {e}")
        return ''

async def get_bot_id_by_short_name(bot_short_name: str, db: AsyncSession) -> int:
    try:
        query = select(TelegramConfig.pk_bot).where(TelegramConfig.bot_short_name == bot_short_name)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_bot_id_by_short_name: {e}")
        return None


async def add_messages(db: AsyncSession, messages_info: List[dict]) -> List[tbl_msg]:
 
    new_messages = []
    for message_info in messages_info:
        message_data = message_info['message_data']
        role = message_info['role']  # Dynamic role assignment
        type = message_info.get('type', 'TEXT')  # Default type is 'TEXT'
        is_processed = message_info.get('is_processed', 'N')  # Default is_processed status
        
        new_message = tbl_msg(
            chat_id=message_data.chat_id,
            user_id=message_data.user_id,
            bot_id=message_data.bot_id,
            content_text=message_data.message_text,
            message_id=message_data.message_id,
            channel=message_data.channel,
            update_id=message_data.update_id,
            message_date=datetime.now(),
            type=type,
            is_processed=is_processed,
            role=role
        )
        db.add(new_message)
        new_messages.append(new_message)

    await db.commit()
    for new_message in new_messages:
        await db.refresh(new_message)

    logger.debug(f"Messages added: {[message.pk_messages for message in new_messages]}")
    return new_messages

async def update_message_content(db: AsyncSession, message_pk: int, new_content: str):
    try:
        query = select(tbl_msg).where(tbl_msg.pk_messages == message_pk)
        result = await db.execute(query)
        message = result.scalar_one_or_none()
        if message:
            message.content_text = new_content
            await db.commit()
            logger.info(f"Updated content_text for message with pk {message_pk}")
        else:
            logger.warning(f"No message found with pk {message_pk}")
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_message_content: {e}")
        raise

async def mark_message_status(db: AsyncSession, message_pk: int, new_status: str):
    try:
        query = select(tbl_msg).where(tbl_msg.pk_messages == message_pk)
        result = await db.execute(query)
        message = result.scalar_one_or_none()
        if message:
            message.is_processed = new_status
            await db.commit()
            logger.info(f"Message with pk {message_pk} marked as {new_status}")
        else:
            logger.warning(f"No message found with pk {message_pk}")
    except SQLAlchemyError as e:
        logger.error(f"Database error in mark_message_status: {e}")
        raise

async def reset_messages_by_chat_id(db: AsyncSession, chat_id: int) -> None:
    try:
        # Select all messages for the given chat_id
        query = select(tbl_msg).where(tbl_msg.chat_id == chat_id)
        result = await db.execute(query)
        messages = result.scalars().all()

        # Check if there are messages to update
        if messages:
            for message in messages:
                message.is_processed = 'R'  # Set status to 'R'
            await db.commit()  # Commit changes to the database

            logger.info(f"All messages for chat_id {chat_id} have been marked as 'R'")
        else:
            logger.warning(f"No messages found for chat_id {chat_id}")

    except SQLAlchemyError as e:
        logger.error(f"Database error in reset_messages_by_chat_id: {e}")
        raise