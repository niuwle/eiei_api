import logging
import os
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import (
    add_messages, get_bot_id_by_short_name, get_bot_token, reset_messages_by_chat_id, mark_chat_as_awaiting
)
from app.controllers.telegram_integration import send_telegram_message, send_generate_options, send_invoice, answer_pre_checkout_query
from app.controllers.message_processing import process_queue
from app.utils.process_audio import transcribe_audio
from app.utils.process_photo import caption_photo
from app.utils.error_handler import handle_exception
logger = logging.getLogger(__name__)


class CallbackQuery(BaseModel):
    id: str
    from_: dict = Field(None, alias='from')
    data: str
    
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

class SuccessfulPayment(BaseModel):
    currency: str
    total_amount: int
    invoice_payload: str
    shipping_option_id: Optional[str] = None
    order_info: Optional[dict] = None
    telegram_payment_charge_id: str
    provider_payment_charge_id: str

class Message(BaseModel):
    message_id: int
    from_: dict = Field(None, alias='from')
    chat: dict
    date: int
    text: Optional[str] = None
    voice: Optional[Voice] = None
    photo: Optional[List[PhotoSize]] = None
    document: Optional[Document] = None
    caption: Optional[str] = None
    successful_payment: Optional[SuccessfulPayment] = None


class PreCheckoutQuery(BaseModel):
    id: str
    from_: dict = Field(..., alias='from')
    currency: str
    total_amount: int
    invoice_payload: str
    shipping_option_id: Optional[str] = None
    order_info: Optional[dict] = None
    
class TelegramWebhookPayload(BaseModel):
    update_id: int
    message: Optional[Message] = None
    callback_query: Optional[CallbackQuery] = None
    pre_checkout_query: Optional[PreCheckoutQuery] = None
    # Ensure SuccessfulPayment is defined in your models
    successful_payment: Optional[SuccessfulPayment] = None
    

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
        user_caption = message_data.caption if message_data.caption else None
        task_params = { 'background_tasks': background_tasks,'bot_id': bot_id, 'chat_id': chat_id, 'db': db, 'user_caption': user_caption}

    elif message_data.document and message_data.document.mime_type.startswith("image/"):
        message_type = 'DOCUMENT'
        process_task = caption_photo
        text_prefix = "[PROCESSING DOCUMENT AS PHOTO]"
        user_caption = message_data.caption if message_data.caption else None
        task_params = {'background_tasks': background_tasks,'bot_id': bot_id, 'chat_id': chat_id, 'db': db,'user_caption': user_caption}

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
        payload = await request.json()
        logger.debug('Raw JSON Payload: %s', payload)

        payload_obj = TelegramWebhookPayload(**payload)  # Parse JSON to Pydantic model
        logger.debug('Parsed Payload: %s', payload_obj.dict())

        bot_id=await get_bot_id_by_short_name(bot_short_name, db)
        
        bot_token=await get_bot_token(bot_id, db)
        
        # Handling callback_query for inline keyboard responses
        if payload.get('callback_query'):
            callback_query = payload['callback_query']
            chat_id = callback_query['message']['chat']['id']
            data = callback_query['data']

            # Depending on the callback data, trigger the corresponding function
            if data == "generate_photo":
                await mark_chat_as_awaiting(db=db, channel="TELEGRAM", chat_id=chat_id, bot_id=bot_id, user_id=callback_query['from']['id'], awaiting_type="PHOTO")
                await send_telegram_message(chat_id=chat_id, text="Please send me the text description for the photo you want to generate", bot_token=bot_token)
            elif data == "generate_audio":
                await mark_chat_as_awaiting(db=db, channel="TELEGRAM",chat_id=chat_id, bot_id=bot_id, user_id=callback_query['from']['id'], awaiting_type="AUDIO")
                await send_telegram_message(chat_id=chat_id, text="Please tell me what you want to hear", bot_token=bot_token)
            
            return {"status": "Callback query processed successfully"}

        # Ensure we're dealing with message updates
        if payload_obj.message:
            chat_id = payload_obj.message.chat['id']

            if payload_obj.message.text == "/generate":
                await send_generate_options(chat_id, bot_token)
                return {"status": "Generate command processed"}

        if payload_obj.message.text == "/getvoice":
            user_id = payload_obj.message.from_.get('id')
            chat_id = payload_obj.message.chat['id']

            # Mark the chat as awaiting voice input in the database
            await mark_chat_as_awaiting(db=db, channel="TELEGRAM",chat_id=chat_id, bot_id=bot_id, user_id=user_id, awaiting_type="AUDIO")

            # Send a prompt to the user asking for the voice input
            await send_telegram_message(chat_id=chat_id, text="Please tell me what you want to hear", bot_token=bot_token)

            return {"status": "Awaiting voice input"}


        if payload_obj.message.text == "/getphoto":
            user_id = payload_obj.message.from_.get('id')
            chat_id = payload_obj.message.chat['id']

            # Mark the chat as awaiting photo input in the database
            await mark_chat_as_awaiting(db=db, channel="TELEGRAM", chat_id=chat_id, bot_id=bot_id, user_id=user_id, awaiting_type="PHOTO")

            # Send a prompt to the user asking for the text input to generate the photo
            await send_telegram_message(chat_id=chat_id, text="Please send me the text description for the photo you want to generate", bot_token=await get_bot_token(await get_bot_id_by_short_name(bot_short_name, db), db))

            return {"status": "Awaiting text input for photo generation"}


        if payload_obj.message.text == "/payment":
            # Code to generate invoice and send it to the user
            prices = [{"label": "Service Fee", "amount": 5000}]
            start_parameter = "payment-example"
            currency = "USD"
            title = "Product Title"
            description = "Product Description"
            payload = "Custom-Payload"
            
            await send_invoice(
                chat_id=chat_id,
                title=title,
                description=description,
                payload=payload,
                currency=currency,
                prices=prices,
                bot_token=bot_token,
                start_parameter=start_parameter,  # This can be '' if you don't need a specific start parameter
                provider_data='',  # Adjust as necessary, or remove if not used
                photo_url='',  # Adjust as necessary, or remove if not used
                photo_size=0,  # Adjust as necessary, or remove if not used
                photo_width=0,  # Adjust as necessary, or remove if not used
                photo_height=0,  # Adjust as necessary, or remove if not used
                need_name=False,  # Adjust as necessary
                need_phone_number=False,  # Adjust as necessary
                need_email=False,  # Adjust as necessary
                need_shipping_address=False,  # Adjust as necessary
                send_phone_number_to_provider=False,  # Adjust as necessary
                send_email_to_provider=False,  # Adjust as necessary
                is_flexible=False,  # Adjust as necessary
                disable_notification=False,  # Adjust as necessary
                protect_content=False,  # Adjust as necessary
                reply_markup=None  # Adjust as necessary, make sure it's a serialized JSON string or None
            )

            return {"status": "generated invoice"}

        # Before the if statement
        logger.debug(f"PreCheckoutQuery data: {payload_obj.pre_checkout_query}")

        if payload_obj.pre_checkout_query:
            pre_checkout_query_id = payload_obj.pre_checkout_query.id
            try:
                await answer_pre_checkout_query(pre_checkout_query_id, ok=True, bot_token=bot_token)
                logger.info(f"PreCheckoutQuery {pre_checkout_query_id} answered successfully.")
            except Exception as e:
                logger.error(f"Failed to answer PreCheckoutQuery {pre_checkout_query_id}: {e}")


            return {"status": "PreCheckoutQuery"}

        if payload_obj.message and payload_obj.message.successful_payment:
            successful_payment = payload_obj.message.successful_payment
            try:
                confirmation_text = "Thank you for your payment!"
                await send_telegram_message(payload_obj.message.chat['id'], confirmation_text, bot_token)
                logger.info(f"Payment confirmed for chat_id {payload_obj.message.chat['id']}.")
            except Exception as e:
                logger.error(f"Failed to process successful payment for chat_id {payload_obj.message.chat['id']}: {e}")

            return {"status": "Payment confirmed "}


        logger.info(f"Incoming payload is not a special case, procesing with handling of chat messages")
        # Pass the Pydantic model, chat_id, message_id, bot_id, bot_short_name, background_tasks, and db to process_message_type
        await process_message_type(payload_obj.message, chat_id, payload_obj.message.message_id, bot_id, bot_short_name, background_tasks, db, payload)


    except Exception as e:
        logger.error(f"An error occurred while processing the request: {e}")
        if chat_id:
            # Use background_tasks to add an error handling task
            background_tasks.add_task(send_error_message_to_user, chat_id, bot_short_name, "Sorry, something went wrong. Please try again later.")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return {"status": "Message processed successfully"}
