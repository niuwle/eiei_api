# In ./app/models/user_info.py
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, TIMESTAMP
from sqlalchemy.sql import func
from . import Base

class tbl_150_user_info(Base):
    __tablename__ = 'tbl_150_user_info'

    pk_user_id = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(BigInteger, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    is_bot = Column(Boolean, nullable=False)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255))
    username = Column(String(255))
    language_code = Column(String(10))
    is_premium = Column(Boolean)
    created_on = Column(TIMESTAMP(timezone=True), server_default=func.now())
    is_banned = Column(Boolean, nullable=False, default=False)
    pk_bot = Column(Integer)
    channel = Column(String(100))
