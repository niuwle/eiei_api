import logging
import os
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import add_messages, get_bot_id_by_short_name, get_bot_token
from app.controllers.telegram_integration import send_telegram_message
from app.controllers.message_processing import process_queue
from app.utils.process_audio import transcribe_audio
from app.utils.process_photo import caption_photo
from app.utils.error_handler import handle_exception

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
    from_: dict = Field(None, alias='from')
    chat: dict
    date: int
    text: str = None
    voice: Voice = None
    photo: List[PhotoSize] = None
    document: Document = None

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
        logger.error(f"Failed to send error message to user due to: {e}")

async def process_message_type(message_data, chat_id, message_id, bot_id, bot_short_name, background_tasks, db, payload):
    message_type, process_task, text_prefix = None, None, ""
    task_params = {} 

    if message_data.text:
        message_type = 'TEXT'
        text_prefix = message_data.text
        if message_data.text == "/start":
            predefined_response_text = "Hi I'm Tabatha! What about you?"
            await send_telegram_message(chat_id, predefined_response_text, await get_bot_token(bot_id, db))
            text_prefix = predefined_response_text
        else:
            process_task = process_queue
            task_params = {'chat_id': chat_id, 'db': db}  # common parameters for process_queue

    elif message_data.photo:
        message_type = 'PHOTO'
        process_task = caption_photo
        text_prefix = "[PROCESSING PHOTO]"
        task_params = { 'background_tasks': background_tasks,'bot_id': bot_id, 'chat_id': chat_id, 'db': db}  # common parameters for caption_photo

    elif message_data.document and message_data.document.mime_type.startswith("image/"):
        message_type = 'DOCUMENT'
        process_task = caption_photo
        text_prefix = "[PROCESSING DOCUMENT AS PHOTO]"
        task_params = {'background_tasks': background_tasks,'bot_id': bot_id, 'chat_id': chat_id, 'db': db}  # common parameters for caption_photo

    elif message_data.voice:
        message_type = 'AUDIO'
        process_task = transcribe_audio
        text_prefix = "[TRANSCRIBING AUDIO]"
        task_params = {'background_tasks': background_tasks, 'bot_id': bot_id, 'chat_id': chat_id, 'db': db}  # common parameters for transcribe_audio

    if message_type:
        # Change payload.update_id to payload['update_id']
        messages_info = [
            {'message_data': TextMessage(chat_id=chat_id, user_id=0, bot_id=bot_id, message_text=text_prefix, message_id=message_id, channel="TELEGRAM", update_id=payload['update_id']), 'type': message_type, 'role': 'USER', 'is_processed': 'N'},
            {'message_data': TextMessage(chat_id=chat_id, user_id=0, bot_id=bot_id, message_text="[AI PLACEHOLDER]", message_id=message_id, channel="TELEGRAM", update_id=payload['update_id']), 'type': 'TEXT', 'role': 'ASSISTANT', 'is_processed': 'S'}
        ]

        added_messages = await add_messages(db, messages_info)
        if process_task and len(added_messages) > 1:
            # Add specific parameters based on the message type
            task_specific_params = {'message_pk': added_messages[0].pk_messages, 'ai_placeholder_pk': added_messages[1].pk_messages}
            if message_data.photo or message_data.voice or message_data.document:
                task_specific_params['file_id'] = message_data.photo[-1].file_id if message_data.photo else message_data.document.file_id if message_data.document else message_data.voice.file_id
            
            all_task_params = {**task_params, **task_specific_params}  # Merge common and specific parameters
            background_tasks.add_task(process_task, **all_task_params)

@router.post("/telegram-webhook/{token}/{bot_short_name}")
async def telegram_webhook(background_tasks: BackgroundTasks, request: Request, token: str, bot_short_name: str, db: AsyncSession = Depends(get_db)):
    chat_id = None # Declare chat_id outside the try block for wider scope
    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    try:
        payload = await request.json() # Define payload here
        # Log the raw JSON payload
        logger.debug('Raw JSON Payload: %s', payload)

        update_id = payload.get('update_id')
        
        # Check if update_id has already been processed
        #existing_msg_query = select(tbl_msg).where(tbl_msg.update_id == update_id)
        #result = await db.execute(existing_msg_query)
        #if result.scalars().first():
        #    logger.info(f"Update ID {update_id} has already been processed. Skipping.")
        #    return {"status": "Update already processed"}
        

        payload_obj = TelegramWebhookPayload(**payload) # Parse JSON to Pydantic model
        # Log the parsed payload
        logger.debug('Parsed Payload: %s', payload_obj.dict())

        chat_id = payload_obj.message.chat['id']
        bot_id = await get_bot_id_by_short_name(bot_short_name, db)

        # Pass the Pydantic model, chat_id, message_id, bot_id, bot_short_name, background_tasks, and db to process_message_type
        await process_message_type(payload_obj.message, chat_id, payload_obj.message.message_id, bot_id, bot_short_name, background_tasks, db, payload)


    except Exception as e:
        logger.error(f"An error occurred while processing the request: {e}")
        if chat_id:
            # Use background_tasks to add an error handling task
            background_tasks.add_task(send_error_message_to_user, chat_id, bot_short_name, "Sorry, something went wrong. Please try again later.")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return {"status": "Message processed successfully"}
