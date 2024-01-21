from sqlalchemy.orm import Session
from app.models.message import tbl_msg
from app.models.telegram_config import TelegramConfig
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import TextMessage

async def get_bot_token(bot_id: int, db: AsyncSession) -> str:
    try:
        result = await db.execute(select(TelegramConfig).filter(TelegramConfig.pk_bot == bot_id))
        bot_config = result.scalar_one_or_none()
        return bot_config.bot_token if bot_config else ''
    except SQLAlchemyError as e:
        logging.error(f"Database error in get_bot_token: {str(e)}")
        return ''

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

async def mark_messages_processed(db: AsyncSession, chat_id: int, bot_id: int):
    try:
        messages_to_update = await db.execute(select(tbl_msg).filter(
            tbl_msg.chat_id == chat_id, 
            tbl_msg.bot_id == bot_id, 
            tbl_msg.is_processed == 'N'
        ))
        for message in messages_to_update.scalars():
            message.is_processed = 'Y'
        await db.commit()
    except SQLAlchemyError as e:
        logging.error(f"Database error in mark_messages_processed: {e}")
        raise

async def mark_messages_pending(db: AsyncSession, chat_id: int, bot_id: int):
    try:
        messages_to_update = await db.execute(select(tbl_msg).filter(
            tbl_msg.chat_id == chat_id, 
            tbl_msg.bot_id == bot_id, 
            tbl_msg.is_processed == 'N'
        ))
        for message in messages_to_update.scalars():
            message.is_processed = 'P'
        await db.commit()
    except SQLAlchemyError as e:
        logging.error(f"Database error in mark_messages_pending: {e}")
        raise
