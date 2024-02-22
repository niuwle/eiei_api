# In ./app/models/payments.py
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from . import Base

class Payment(Base):
    __tablename__ = 'tbl_400_payments'

    pk_payment = Column(Integer, primary_key=True, autoincrement=True)
    update_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    user_is_bot = Column(Boolean, default=False)
    user_first_name = Column(String(100))
    user_language_code = Column(String(10))
    chat_id = Column(BigInteger, nullable=False)
    chat_first_name = Column(String(100))
    chat_type = Column(String(50), nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow)
    currency = Column(String(10))
    total_amount = Column(Float)
    invoice_payload = Column(String(4000))
    telegram_payment_charge_id = Column(String(400))
    provider_payment_charge_id = Column(String(400))
    created_on = Column(DateTime, default=datetime.utcnow)
    updated_on = Column(DateTime, onupdate=datetime.utcnow)
