# app/database_operations.py
from sqlalchemy.orm import Session
from app.models.message import tbl_msg
from app.models.telegram_config import TelegramConfig
from datetime import datetime


def get_bot_token(bot_id: int, db: Session) -> str:
    bot_config = db.query(TelegramConfig).filter(TelegramConfig.pk_bot == bot_id).first()
    return bot_config.bot_token if bot_config else ''

def insert_response_message(db: Session, channel: str, bot_id: int, chat_id: int, content_text: str, type: str, role: str, is_processed: str):
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
    db.commit()

    
def add_message(db, message_data):
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
    db.commit()
    db.refresh(db_message)
    return db_message
    
def mark_messages_processed(db: Session, chat_id: int, bot_id: int):
    messages_to_update = db.query(tbl_msg).filter(
        tbl_msg.chat_id == chat_id, 
        tbl_msg.bot_id == bot_id, 
        tbl_msg.is_processed == 'N'
    )
    for message in messages_to_update:
        message.is_processed = 'Y'
    db.commit()
