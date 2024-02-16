# ./app/controllers/telegram_webhook.py
import logging
import os
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import (
    add_messages,
    get_bot_id_by_short_name,
    get_bot_token,
    reset_messages_by_chat_id,
    mark_chat_as_awaiting,
)
from app.controllers.telegram_integration import send_telegram_message
from app.controllers.message_processing import process_queue
from app.utils.process_audio import transcribe_audio
from app.utils.process_photo import caption_photo

logger = logging.getLogger(__name__)


class Voice(BaseModel):
    duration: int
    mime_type: str
    file_id: str
    file_size: int


class PhotoSize(BaseModel):
    file_id: str
    file_unique_id: str
    file_size: int
    width: int
    height: int


class Document(BaseModel):
    file_id: str
    file_unique_id: str
    file_size: int
    file_name: str
    mime_type: str
    thumb: PhotoSize = None


class Message(BaseModel):
    message_id: int
    from_: dict = Field(None, alias="from")
    chat: dict
    date: int
    text: str = None
    voice: Voice = None
    photo: List[PhotoSize] = None
    document: Document = None
    caption: str = None


class TelegramWebhookPayload(BaseModel):
    update_id: int
    message: Message


router = APIRouter()
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")


async def send_error_message_to_user(chat_id: int, bot_short_name: str, message: str):
    try:
        async with get_db() as db:
            bot_id = await get_bot_id_by_short_name(bot_short_name, db)
            bot_token = await get_bot_token(bot_id, db)
            await send_telegram_message(chat_id, message, bot_token)
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")


async def process_message_type(
    message_data,
    chat_id,
    message_id,
    bot_id,
    bot_short_name,
    background_tasks,
    db,
    payload,
):
    logger.debug(f"Processing message type for chat_id={chat_id}")
    task_params, process_task = {}, None
    if message_data.text:
        process_task, text_prefix = process_queue, message_data.text[:100]
    elif message_data.photo or (
        message_data.document and message_data.document.mime_type.startswith("image/")
    ):
        process_task, text_prefix = caption_photo, "[PROCESSING PHOTO]"
    elif message_data.voice:
        process_task, text_prefix = transcribe_audio, "[TRANSCRIBING AUDIO]"
    messages_info = [
        {
            "message_data": TextMessage(
                chat_id=chat_id,
                user_id=0,
                bot_id=bot_id,
                message_text=text_prefix,
                message_id=message_id,
                channel="TELEGRAM",
                update_id=payload["update_id"],
            ),
            "type": "TEXT",
            "role": "USER",
            "is_processed": "N",
        },
        {
            "message_data": TextMessage(
                chat_id=chat_id,
                user_id=0,
                bot_id=bot_id,
                message_text="[AI PLACEHOLDER]",
                message_id=message_id,
                channel="TELEGRAM",
                update_id=payload["update_id"],
            ),
            "type": "TEXT",
            "role": "ASSISTANT",
            "is_processed": "S",
        },
    ]
    added_messages = await add_messages(db, messages_info)
    if process_task:
        background_tasks.add_task(
            process_task,
            **{
                "chat_id": chat_id,
                "db": db,
                "message_pk": added_messages[0].pk_messages,
                "ai_placeholder_pk": added_messages[1].pk_messages,
            },
        )


@router.post("/telegram-webhook/{token}/{bot_short_name}")
async def telegram_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
    token: str,
    bot_short_name: str,
    db: AsyncSession = Depends(get_db),
):
    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    payload = await request.json()
    logger.debug(f"Received payload: {payload}")
    try:
        payload_obj = TelegramWebhookPayload(**payload)
        if payload_obj.message.text in ["/reset", "/getvoice", "/getphoto"]:
            logger.debug(f"Special command detected: {payload_obj.message.text}")
        await process_message_type(
            payload_obj.message,
            payload_obj.message.chat["id"],
            payload_obj.message.message_id,
            await get_bot_id_by_short_name(bot_short_name, db),
            bot_short_name,
            background_tasks,
            db,
            payload,
        )
    except Exception as e:
        logger.error(f"Processing error: {e}")
        chat_id = payload.get("message", {}).get("chat", {}).get("id", None)
        if chat_id:
            background_tasks.add_task(
                send_error_message_to_user,
                chat_id,
                bot_short_name,
                "Sorry, something went wrong.",
            )
        raise HTTPException(status_code=500, detail="Internal Server Error")
    return {"status": "Message processed"}
