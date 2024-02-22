
# In ./app/models/user_credits.py
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from app.models.payments import Payment
from datetime import datetime
from . import Base

class UserCredit(Base):
    __tablename__ = 'tbl_450_user_credits'

    pk_credit = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(100))
    pk_bot = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    credits = Column(Float)
    transaction_type = Column(String(100))
    transaction_date = Column(DateTime, default=datetime.utcnow)
    pk_payment = Column(BigInteger)
    total_credits = Column(BigInteger)
    