# app/utilities.py
from sqlalchemy.orm import Session
from app.models.telegram_config import TelegramConfig  # Assuming you have this model
from app.models.message import tbl_msg
from datetime import datetime

