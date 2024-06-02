# app/models/telegram_config.py
from sqlalchemy import Column, Integer, String, DateTime
from . import Base

class TelegramConfig(Base):
    __tablename__ = 'tbl_100_telegram_config'

    pk_bot = Column(Integer, primary_key=True, index=True)
    bot_name = Column(String(100))
    bot_short_name = Column(String(100))
    bot_description = Column(String(4000))
    bot_token = Column(String(4000))
    bot_voice_id = Column(String(4000))
    bot_assistant_prompt = Column(String(4000))
    bot_pre_prompt = Column(String(4000))
    bot_greeting_msg = Column(String(4000))
    bot_temperature = Column(Integer)
    bot_presence_penalty = Column(Integer)
    bot_frequency_penalty = Column(Integer)
    bot_default_reply = Column(String(4000))
    created_by = Column(String(1000))
    created_on = Column(DateTime)
    updated_by = Column(String(1000))
    updated_on = Column(DateTime)
    
