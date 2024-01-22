# app/routers/telegram-webhook.py
from fastapi import APIRouter, HTTPException
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import add_message
from pydantic import BaseModel
import os

class TelegramWebhookPayload(BaseModel):
    update_id: int
    message: dict

router = APIRouter()
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")

@router.post("/telegram-webhook/{token}")
async def telegram_webhook(token: str, payload: TelegramWebhookPayload):
    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    if not payload.message.get('text'):
        raise HTTPException(status_code=400, detail="No text found in message")

    chat_id = payload.message['chat']['id']
    message_text = payload.message['text']
    message_id = payload.message['message_id']

    internal_message = TextMessage(
        chat_id=chat_id, user_id=0, bot_id=0, 
        message_text=message_text, message_id=message_id, 
        channel="TELEGRAM", update_id=payload.update_id
    )

    async with get_db() as db:
        await add_message(db, internal_message)
        return {"status": "Message processed successfully"}

