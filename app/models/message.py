#app/models/message.py
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from . import Base

class tbl_msg(Base):
    __tablename__ = 'tbl_200_messages'

    pk_messages = Column(Integer, primary_key=True, index=True)  # Changed from id to pk_messages
    channel = Column(String(100))
    bot_id = Column(BigInteger, nullable=False) # NOT NULL constraint specified here
    chat_id = Column(BigInteger)
    user_id = Column(BigInteger)
    type = Column(String(100))
    role = Column(String(100))
    content_text = Column(String(4000))
    file_id = Column(String(4000))
    message_date = Column(DateTime) # This matches the TIMESTAMP in your SQL
    update_id = Column(BigInteger)
    message_id = Column(BigInteger)
    is_processed = Column(String(1))
    is_reset = Column(String(1))
    created_by = Column(String(1000))
    created_on = Column(DateTime, default=func.now()) # Default to the current timestamp
    updated_by = Column(String(1000))
    updated_on = Column(DateTime, default=func.now(), onupdate=func.now()) # Updated timestamp on update
