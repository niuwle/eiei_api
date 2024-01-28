# app/routers/telegram-webhook.py
import logging
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import add_message, get_bot_id_by_short_name
from app.controllers.message_processing import process_queue
from app.utils.transcribe_audio import transcribe_audio
import os

logger = logging.getLogger(__name__)

class Voice(BaseModel):
    duration: int
    mime_type: str
    file_id: str
    file_size: int

class Message(BaseModel):
    message_id: int
    from_: dict = Field(None, alias='from')
    chat: dict
    date: int
    text: str = None  # Make text optional
    voice: Voice = None  # Add voice field

class TelegramWebhookPayload(BaseModel):
    update_id: int
    message: Message

router = APIRouter()
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")

@router.post("/telegram-webhook/{token}/{bot_short_name}")
async def telegram_webhook(background_tasks: BackgroundTasks, request: Request, token: str, bot_short_name: str):
    raw_body = await request.body()
    logger.info(f"Raw JSON payload: {raw_body.decode('utf-8')}")

    try:
        payload_dict = await request.json()
        payload = TelegramWebhookPayload(**payload_dict)
    except Exception as e:
        logger.error(f"Error parsing request body: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    message_data = payload.message
    chat_id = message_data.chat['id']
    message_id = message_data.message_id

    async with get_db() as db:
        bot_id = await get_bot_id_by_short_name(bot_short_name, db)

        if message_data.voice:
            # Handle voice message
            internal_message = TextMessage(
                chat_id=chat_id, user_id=0, bot_id=bot_id,
                message_text="[TRANSCRIBING AUDIO]", message_id=message_id,
                channel="TELEGRAM", update_id=payload.update_id
            )
            added_message = await add_message(db, internal_message,'VOICE','N','USER')
            # Start transcription process in the background
            background_tasks.add_task(transcribe_audio,  background_tasks, added_message.pk_messages,bot_id,chat_id, message_data.voice.file_id, db)
            #background_tasks.add_task(process_queue, added_message.chat_id, db)
        elif message_data.text:
            # Handle text message
            internal_message = TextMessage(
                chat_id=chat_id, user_id=0, bot_id=bot_id,
                message_text=message_data.text, message_id=message_id,
                channel="TELEGRAM", update_id=payload.update_id
            )
            added_message = await add_message(db, internal_message,'TEXT','N','USER')
            background_tasks.add_task(process_queue, added_message.chat_id, db)
        else:
            # If neither text nor voice is found
            raise HTTPException(status_code=400, detail="Unsupported message type")

        return {"pk_messages": added_message.pk_messages, "status": "Message processed successfully"}

