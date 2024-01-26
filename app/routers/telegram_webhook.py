# app/routers/telegram-webhook.py
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import add_message, get_bot_id_by_short_name
from app.controllers.message_processing import process_queue
import os

logger = logging.getLogger(__name__)

class TelegramWebhookPayload(BaseModel):
    message_id: int
    from_: dict = Field(None, alias='from')  # Updated to use Field with alias
    chat: dict
    date: int
    text: str



router = APIRouter()
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")

@router.post("/telegram-webhook/{token}/{bot_short_name}")
async def telegram_webhook(request: Request, token: str, bot_short_name: str):  # Accept Request object
    # Read and log the raw request body
    raw_body = await request.body()
    logger.info(f"Raw JSON payload: {raw_body.decode('utf-8')}")  # Decode to log as a string

    # Now parse the body as your Pydantic model
    try:
        payload = await request.json()  # Parse JSON body to dict
        payload = TelegramWebhookPayload(**payload)  # Convert dict to Pydantic model
    except Exception as e:
        logger.error(f"Error parsing request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")

    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    if not payload.text:
        raise HTTPException(status_code=400, detail="No text found in message")

    chat_id = payload.chat['id']
    message_text = payload.text
    message_id = payload.message_id

    async with get_db() as db:
        bot_id = await get_bot_id_by_short_name(bot_short_name, db)

        internal_message = TextMessage(
            chat_id=chat_id, user_id=0, bot_id=bot_id,
            message_text=message_text, message_id=message_id,
            channel="TELEGRAM", update_id=0
        )

        try:
            added_message = await add_message(db, internal_message)
            await process_queue(added_message.chat_id, db)
            return {"pk_messages": added_message.pk_messages, "status": "Message saved successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
