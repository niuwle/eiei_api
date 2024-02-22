
# In ./app/models/user_credits.py
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from .payments import Payment  
from datetime import datetime

Base = declarative_base()

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
    pk_payment = Column(Integer, ForeignKey('tbl_300_payments.pk_payment'))
    payment = relationship("Payment", back_populates="user_credits")

Payment.user_credits = relationship("UserCredit", order_by=UserCredit.pk_credit, back_populates="payment")
