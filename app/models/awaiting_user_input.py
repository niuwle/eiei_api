#app/models/awaiting_user_input.py
from sqlalchemy import Column, BigInteger, String, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class tbl_300_awaiting_user_input(Base):
    __tablename__ = 'tbl_300_awaiting_user_input'
    
    pk_user_status = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(100))
    bot_id = Column(BigInteger)
    user_id = Column(BigInteger)
    chat_id = Column(BigInteger)
    awaiting_type = Column(String(100))
    status = Column(String(100))

    def __repr__(self):
        return f"<tbl_300_awaiting_user_input(pk_user_status={self.pk_user_status}, channel='{self.channel}', bot_id={self.bot_id}, user_id={self.user_id}, chat_id={self.chat_id}, awaiting_type='{self.awaiting_type}', status='{self.status}')>"
