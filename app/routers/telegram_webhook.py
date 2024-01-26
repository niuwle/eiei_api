# app/routers/telegram-webhook.py
import logging
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import add_message, get_bot_id_by_short_name
from app.controllers.message_processing import process_queue
import os

logger = logging.getLogger(__name__)

class Message(BaseModel):
    message_id: int
    from_: dict = Field(None, alias='from')  # Using from_ to avoid conflict with Python keyword 'from'
    chat: dict
    date: int
    text: str

class TelegramWebhookPayload(BaseModel):
    update_id: int
    message: Message

router = APIRouter()
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")

@router.post("/telegram-webhook/{token}/{bot_short_name}")
async def telegram_webhook(background_tasks: BackgroundTasks, request: Request, token: str, bot_short_name: str):

    # Read and log the raw request body
    raw_body = await request.body()
    logger.info(f"Raw JSON payload: {raw_body.decode('utf-8')}")

    # Parse the body as your Pydantic model
    try:
        payload_dict = await request.json()  # Parse JSON body to dict
        payload = TelegramWebhookPayload(**payload_dict)  # Convert dict to Pydantic model
    except Exception as e:
        logger.error(f"Error parsing request body: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    # Accessing 'text' from the nested 'message' object
    if not payload.message.text:
        raise HTTPException(status_code=400, detail="No text found in message")

    message_data = payload.message
    chat_id = message_data.chat['id']
    message_text = message_data.text
    message_id = message_data.message_id
    
    async with get_db() as db:
        bot_id = await get_bot_id_by_short_name(bot_short_name, db)

        internal_message = TextMessage(
            chat_id=chat_id, user_id=0, bot_id=bot_id,
            message_text=message_text, message_id=message_id,
            channel="TELEGRAM", update_id=payload.update_id  # Use the update_id from the payload
        )

        try:
            added_message = await add_message(db, internal_message)
            background_tasks.add_task(process_queue, added_message.chat_id, db)
            return {"pk_messages": added_message.pk_messages, "status": "Message saved successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")