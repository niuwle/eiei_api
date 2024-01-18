#app/schemas.py
from pydantic import BaseModel
from datetime import datetime

class TextMessage(BaseModel):
    chat_id: int
    user_id: int
    bot_id: int
    message_text: str
    message_id: int
    channel: str
    update_id: int
