# app/routers/telegram-webhook.py
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import add_messages, get_bot_id_by_short_name, get_bot_token
from app.controllers.telegram_integration import send_telegram_message
from app.controllers.message_processing import process_queue
from app.utils.process_audio import transcribe_audio
from app.utils.process_photo import caption_photo
from app.utils.error_handler import handle_exception 
import os


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


@router.post("/telegram-webhook/{token}/{bot_short_name}")
async def telegram_webhook(background_tasks: BackgroundTasks, request: Request, token: str, bot_short_name: str):
        
    chat_id = None  # Initialize chat_id to ensure it's available for error handling

    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    raw_body = await request.body()
    logger.info(f"Raw JSON payload: {raw_body.decode('utf-8')}")

    try:
        payload_dict = await request.json()
        payload = TelegramWebhookPayload(**payload_dict)
        message_data = payload.message
        chat_id = message_data.chat['id']
        message_id = message_data.message_id
        
        async with get_db() as db:
            bot_id = await get_bot_id_by_short_name(bot_short_name, db)

            # Check if the message is a '/start' bot command
            if message_data.text == "/start": # and message_data.entities:
                #for entity in message_data.entities:
                    #if entity.type == "bot_command" and message_data.text[entity.offset:entity.offset+entity.length] == "/start":

                        bot_token = await get_bot_token(bot_id, db)
                        predefined_response_text = "Hi I'm Tabatha! What about you?"  # Customize this message
                        await send_telegram_message(chat_id, predefined_response_text, bot_token)

                        # Create a TextMessage instance with the predefined response
                        response_message = TextMessage(
                            chat_id=chat_id, user_id=0, bot_id=bot_id,
                            message_text=predefined_response_text, message_id=message_id,
                            channel="TELEGRAM", update_id=payload.update_id
                        )

                        # Add the predefined response to the database
                        added_message = await add_messages(db, response_message, 'TEXT', 'Y', 'ASSISTANT')
                        
                        return {"status": "Predefined start message sent"}

            elif message_data.photo:
                # Handle photo message
                largest_photo = message_data.photo[-1]  # Assuming the last photo is the largest

                messages_info = [
                    {
                        'message_data': TextMessage(
                            chat_id=chat_id, user_id=0, bot_id=bot_id,
                            message_text="[PROCESSING PHOTO]", message_id=message_id,
                            channel="TELEGRAM", update_id=payload.update_id
                        ),
                        'type': 'PHOTO',
                        'role': 'USER',
                        'is_processed': 'N'
                    },
                    {
                        'message_data': TextMessage(
                            chat_id=chat_id, user_id=0, bot_id=bot_id,
                            message_text="[AI PLACEHOLDER]", message_id=message_id,
                            channel="TELEGRAM", update_id=payload.update_id
                        ),
                        'type': 'TEXT',
                        'role': 'USER',
                        'is_processed': 'P'
                    }
                ]

                # Add messages
                added_messages = await add_messages(db, messages_info)

                # Split PKs into two variables
                user_msg_pk = added_messages[0].pk_messages if added_messages else None
                ai_placeholder_pk = added_messages[1].pk_messages if len(added_messages) > 1 else None

                # Use the PKs as needed
                if user_msg_pk and ai_placeholder_pk:
                        
                    background_tasks.add_task(caption_photo, background_tasks, added_message.pk_messages, ai_placeholder_rec.pk_messages, bot_id, chat_id, largest_photo.file_id, db)
                else:
                    logger.error("Failed to add messages to the database.")
                    
            # New check for document message
            elif message_data.document and message_data.document.mime_type.startswith("image/"):
                messages_info = [
                    {
                        'message_data': TextMessage(
                            chat_id=chat_id, user_id=0, bot_id=bot_id,
                            message_text="[PROCESSING DOCUMENT AS PHOTO]", message_id=message_id,
                            channel="TELEGRAM", update_id=payload.update_id
                        ),
                        'type': 'DOCUMENT',
                        'role': 'USER',
                        'is_processed': 'N'
                    },
                    {
                        'message_data': TextMessage(
                            chat_id=chat_id, user_id=0, bot_id=bot_id,
                            message_text="[AI PLACEHOLDER]", message_id=message_id,
                            channel="TELEGRAM", update_id=payload.update_id
                        ),
                        'type': 'TEXT',
                        'role': 'USER',
                        'is_processed': 'P'
                    }
                ]

                # Add messages
                added_messages = await add_messages(db, messages_info)

                # Split PKs into two variables
                user_msg_pk = added_messages[0].pk_messages if added_messages else None
                ai_placeholder_pk = added_messages[1].pk_messages if len(added_messages) > 1 else None

                # Use the PKs as needed
                if user_msg_pk and ai_placeholder_pk:
                    
                    background_tasks.add_task(caption_photo, background_tasks, added_message.pk_messages, ai_placeholder_rec.pk_messages, bot_id, chat_id, document.file_id, db)
                else:
                    logger.error("Failed to add messages to the database.")

            elif message_data.voice:
                # Prepare messages with dynamic roles
                messages_info = [
                    {
                        'message_data': TextMessage(
                            chat_id=chat_id, user_id=0, bot_id=bot_id,
                            message_text="[TRANSCRIBING AUDIO]", message_id=message_id,
                            channel="TELEGRAM", update_id=payload.update_id
                        ),
                        'type': 'AUDIO',
                        'role': 'USER',
                        'is_processed': 'N'
                    },
                    {
                        'message_data': TextMessage(
                            chat_id=chat_id, user_id=0, bot_id=bot_id,
                            message_text="[AI PLACEHOLDER]", message_id=message_id,
                            channel="TELEGRAM", update_id=payload.update_id
                        ),
                        'type': 'TEXT',
                        'role': 'USER',
                        'is_processed': 'P'
                    }
                ]

                # Add messages
                added_messages = await add_messages(db, messages_info)

                # Split PKs into two variables
                user_msg_pk = added_messages[0].pk_messages if added_messages else None
                ai_placeholder_pk = added_messages[1].pk_messages if len(added_messages) > 1 else None

                # Use the PKs as needed
                if user_msg_pk and ai_placeholder_pk:
                    background_tasks.add_task(transcribe_audio,  background_tasks, added_message.pk_messages, ai_placeholder_rec.pk_messages, bot_id,chat_id, message_data.voice.file_id, db)
                else:
                    logger.error("Failed to add messages to the database.")

            elif message_data.text:
                # Prepare messages with dynamic roles
                messages_info = [
                    {
                        'message_data': TextMessage(
                            chat_id=chat_id, user_id=0, bot_id=bot_id,
                            message_text=message_data.text, message_id=message_id,
                            channel="TELEGRAM", update_id=payload.update_id
                        ),
                        'type': 'TEXT',
                        'role': 'USER',
                        'is_processed': 'N'
                    },
                    {
                        'message_data': TextMessage(
                            chat_id=chat_id, user_id=0, bot_id=bot_id,
                            message_text="[AI PLACEHOLDER]", message_id=message_id,
                            channel="TELEGRAM", update_id=payload.update_id
                        ),
                        'type': 'TEXT',
                        'role': 'USER',
                        'is_processed': 'P'
                    }
                ]

                # Add messages
                added_messages = await add_messages(db, messages_info)

                # Split PKs into two variables
                user_msg_pk = added_messages[0].pk_messages if added_messages else None
                ai_placeholder_pk = added_messages[1].pk_messages if len(added_messages) > 1 else None

                # Use the PKs as needed
                if user_msg_pk and ai_placeholder_pk:
                    background_tasks.add_task(process_queue, chat_id,  ai_placeholder_pk, db)
                else:
                    logger.error("Failed to add messages to the database.")

    except Exception as e:
        logger.error(f"An error occurred while processing the request: {e}")
        if chat_id:
            background_tasks.add_task(send_error_message_to_user, chat_id, bot_short_name, "Sorry, something went wrong. Please try again later.")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return {"status": "Message processed successfully"}
