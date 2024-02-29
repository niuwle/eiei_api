import logging
import os
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import (
    insert_user_if_not_exists, is_user_banned, add_messages, get_bot_id_by_short_name, get_bot_token, reset_messages_by_chat_id, mark_chat_as_awaiting, get_latest_total_credits, add_payment_details, update_user_credits
)
from app.controllers.telegram_integration import send_credit_count, send_telegram_message, send_credit_purchase_options, send_generate_options, send_invoice, answer_pre_checkout_query
from app.controllers.message_processing import process_queue
from app.utils.process_audio import transcribe_audio
from app.utils.process_photo import caption_photo

from decimal import Decimal

from datetime import datetime
from app.utils.error_handler import error_handler, send_error_notification

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
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

class CallbackQuery(BaseModel):
    id: str
    from_: dict = Field(None, alias='from')
    message: Optional[Message] = None  # Ensure Message is defined as per your existing model
    data: str

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
    #successful_payment: Optional[SuccessfulPayment] = None
    

router = APIRouter()
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")



async def process_message_type(message_data, chat_id, user_id, message_id, bot_id, bot_short_name, background_tasks, db, payload):
    message_type, process_task, text_prefix = None, None, ""
    task_params = {} 

    # Check if the message text starts with "/" and is not a recognized command
    if message_data.text and message_data.text.startswith("/") and message_data.text not in ["/start", "/generate", "/getvoice", "/getphoto", "/credits", "/payment", "/reset"]:
        # Log the ignored unknown command for debugging purposes
        logger.info(f"Ignoring unknown command: {message_data.text}")
        return  # Ignore the message and return early

    if message_data.text:
        message_type = 'TEXT'
        text_prefix = message_data.text
        if message_data.text == "/start":
            predefined_response_text = "Hi I'm Tabatha! What about you?"
            await send_telegram_message(chat_id, predefined_response_text, await get_bot_token(bot_id, db))
            text_prefix = predefined_response_text
        else:
            process_task = process_queue
            task_params = {'chat_id': chat_id, 'bot_id': bot_id,'user_id': user_id, 'db': db}  # common parameters for process_queue

    elif message_data.photo:
        message_type = 'PHOTO'
        process_task = caption_photo
        text_prefix = "[PROCESSING PHOTO]"
        user_caption = message_data.caption if message_data.caption else None
        task_params = { 'background_tasks': background_tasks,'bot_id': bot_id, 'chat_id': chat_id, 'user_id': user_id, 'db': db, 'user_caption': user_caption}

    elif message_data.document and message_data.document.mime_type.startswith("image/"):
        message_type = 'DOCUMENT'
        process_task = caption_photo
        text_prefix = "[PROCESSING DOCUMENT AS PHOTO]"
        user_caption = message_data.caption if message_data.caption else None
        task_params = {'background_tasks': background_tasks,'bot_id': bot_id, 'chat_id': chat_id, 'user_id': user_id, 'db': db,'user_caption': user_caption}

    elif message_data.voice:
        message_type = 'AUDIO'
        process_task = transcribe_audio
        text_prefix = "[TRANSCRIBING AUDIO]"
        task_params = {'background_tasks': background_tasks, 'bot_id': bot_id, 'chat_id': chat_id, 'user_id': user_id, 'db': db}  # common parameters for transcribe_audio

    if message_type:
        
        messages_info = [
            {'message_data': TextMessage(chat_id=chat_id, user_id=user_id, bot_id=bot_id, message_text=text_prefix, message_id=message_id, channel="TELEGRAM", update_id=payload['update_id']), 'type': message_type, 'role': 'USER', 'is_processed': 'N'},
            {'message_data': TextMessage(chat_id=chat_id, user_id=user_id, bot_id=bot_id, message_text="[AI PLACEHOLDER]", message_id=message_id, channel="TELEGRAM", update_id=payload['update_id']), 'type': 'TEXT', 'role': 'ASSISTANT', 'is_processed': 'S'}
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
@error_handler
async def telegram_webhook(background_tasks: BackgroundTasks, request: Request, token: str, bot_short_name: str, db: AsyncSession = Depends(get_db)):
    chat_id = None  # Declare chat_id outside the try block for wider scope
    user_id = None  # Similarly, declare user_id for broader access
    bot_token = None  # Similarly, declare bot_token for broader access
    if token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    try:
        payload = await request.json()
        logger.debug('Raw JSON Payload: %s', payload)
        payload_obj = TelegramWebhookPayload(**payload)

        logger.debug('Parsed Payload: %s', payload_obj.dict())
        bot_id = await get_bot_id_by_short_name(bot_short_name, db)
        bot_token = await get_bot_token(bot_id, db)

        if payload_obj.message and payload_obj.message.from_:
            chat_id = payload_obj.message.chat.get('id')
            user_id = payload_obj.message.from_.get('id')
            
            # Perform the credit check after determining user_id and chat_id
            total_credits = await get_latest_total_credits(db=db, user_id=user_id, bot_id=bot_id)
            if total_credits < Decimal('0'):
                # User does not have enough credits, send a message and stop further processing
                await send_telegram_message(chat_id, "You don't have enough credits to perform this operation.", bot_token)
                await send_credit_count(chat_id=chat_id, bot_token=bot_token, total_credits=total_credits)
                return {"status": "Insufficient credits"}
            # Use the username as a fallback for last_name if last_name is not provided
            last_name_or_username = payload_obj.message.from_.get('last_name', payload_obj.message.from_.get('username', ''))
            user_data = {
                'id': payload_obj.message.from_.get('id'),
                'channel': 'TELEGRAM',
                'is_bot': payload_obj.message.from_.get('is_bot', False),
                'first_name': payload_obj.message.from_.get('first_name', ''),
                'last_name': payload_obj.message.from_.get('last_name', ''),  
                'username': payload_obj.message.from_.get('username', ''),  # Optional, defaulting to empty string as it's not provided
                'language_code': payload_obj.message.from_.get('language_code', ''),  # Optional, using .get() in case it's not present
                'is_premium': False,  # Optional, defaulting to False as it's not provided
                'pk_bot': bot_id,  # Adding the bot_id as pk_bot
                'chat_id': chat_id  # Adding chat_id
            }

            # Insert the user if not exists and check if banned
            inserted = await insert_user_if_not_exists(db, user_data)
            if inserted:
                logger.info(f"User {user_data['id']} inserted.")
            else:
                logger.info(f"User {user_data['id']} already exists.")

            if await is_user_banned(db, user_data['id'],bot_id , 'TELEGRAM'):

                await send_error_notification(chat_id, bot_short_name, "Your account is banned.")
                
                return {"status": "User is banned"}


        # Handling callback_query for inline keyboard responses
        if 'callback_query' in payload:
            callback_query = payload['callback_query']
            chat_id = callback_query['message']['chat']['id']
            user_id = callback_query['from']['id']
            data = callback_query['data']

            if data.startswith("buy_"):
                credit_amounts = {
                    "buy_100_credits": 500,
                    "buy_500_credits": 2000,
                    "buy_1000_credits": 3500
                }
                titles = {
                    "buy_100_credits": "💎 100 Credits - Unlock More Fun!",
                    "buy_500_credits": "🚀 500 Credits - Boost Your Power!",
                    "buy_1000_credits": "🌌 1000 Credits - Ultimate Experience!"
                }
                descriptions = {
                    "buy_100_credits": "Dive into endless fun with 100 credits.",
                    "buy_500_credits": "Amplify the thrill with 500 credits.",
                    "buy_1000_credits": "Unlock all features with 1000 credits!"
                }

                amount = credit_amounts.get(data, 0)
                title = titles.get(data, "Credits Pack")
                description = descriptions.get(data, "Get more credits for more interaction.")

                prices = [{"label": "Service Fee", "amount": amount}]
                currency = "USD"
                payload = data

                await send_invoice(
                    chat_id=chat_id,
                    title=title,
                    description=description,
                    payload=payload,
                    currency=currency,
                    prices=prices,
                    bot_token=bot_token,
                    start_parameter="example"
                )
                
            data = payload_obj.callback_query.data

            # Depending on the callback data, trigger the corresponding function
            if data == "generate_photo":
                await mark_chat_as_awaiting(db=db, channel="TELEGRAM", chat_id=chat_id, bot_id=bot_id, user_id=user_id, awaiting_type="PHOTO")
                await send_telegram_message(chat_id=chat_id, text="Please send me the text description for the photo you want to generate", bot_token=bot_token)
            
            if data == "generate_audio":
                await mark_chat_as_awaiting(db=db, channel="TELEGRAM", chat_id=chat_id, bot_id=bot_id, user_id=user_id, awaiting_type="AUDIO")
                await send_telegram_message(chat_id=chat_id, text="Please tell me what you want to hear", bot_token=bot_token)
           
            if data == "ask_credit":
                await send_credit_purchase_options(chat_id, bot_token)
           
            return {"status": "Callback query processed successfully"}


        if payload_obj.message and payload_obj.message.from_:
            user_id = payload_obj.message.from_.get('id')
            chat_id = payload_obj.message.chat['id']

        # Ensure we're dealing with message updates

        if payload_obj.message and payload_obj.message.text == "/generate":
        
            await send_generate_options(chat_id, bot_token)
            return {"status": "Generate command processed"}

        if payload_obj.message and payload_obj.message.text == "/getvoice":

            # Mark the chat as awaiting voice input in the database
            await mark_chat_as_awaiting(db=db, channel="TELEGRAM",chat_id=chat_id, bot_id=bot_id, user_id=user_id, awaiting_type="AUDIO")

            # Send a prompt to the user asking for the voice input
            await send_telegram_message(chat_id=chat_id, text="Please tell me what you want to hear", bot_token=bot_token)

            return {"status": "Awaiting voice input"}


        if payload_obj.message and payload_obj.message.text == "/getphoto":

            # Mark the chat as awaiting photo input in the database
            await mark_chat_as_awaiting(db=db, channel="TELEGRAM", chat_id=chat_id, bot_id=bot_id, user_id=user_id, awaiting_type="PHOTO")

            # Send a prompt to the user asking for the text input to generate the photo
            await send_telegram_message(chat_id=chat_id, text="Please send me the text description for the photo you want to generate", bot_token=await get_bot_token(await get_bot_id_by_short_name(bot_short_name, db), db))

            return {"status": "Awaiting text input for photo generation"}

        if payload_obj.message and payload_obj.message.text == "/credits":

            # Retrieve the total credits for the user
            await send_credit_count(chat_id=chat_id, bot_token=bot_token, total_credits=await get_latest_total_credits(db=db,  user_id=user_id, bot_id=bot_id))
            return {"status": "Credits information sent"}
            
        if payload_obj.message and payload_obj.message.text == "/payment":
            
            await send_credit_purchase_options(chat_id, bot_token)
            return {"status": "Payment command processed"}


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


        # Inside your successful payment handling block
        if payload_obj.message and payload_obj.message.successful_payment:
            successful_payment = payload_obj.message.successful_payment
            invoice_payload = successful_payment.invoice_payload  # This is your key to determine the purchase
            
            # Example mapping of invoice_payload to credits
            credits_options = {
                "buy_100_credits": 100,
                "buy_500_credits": 500,
                "buy_1000_credits": 1000,
            }

            # Determine the number of credits based on the invoice_payload
            credits_to_add = credits_options.get(invoice_payload, 0)  # Default to 0 if not found
            
            
            payment_info = {
                "update_id": payload_obj.update_id,
                "message_id": payload_obj.message.message_id,
                "user_id": payload_obj.message.from_.get('id'),
                "user_is_bot": payload_obj.message.from_.get('is_bot', False),
                "user_first_name": payload_obj.message.from_.get('first_name', ''),
                "user_language_code": payload_obj.message.from_.get('language_code', ''),
                "chat_id": payload_obj.message.chat.get('id'),
                "chat_first_name": payload_obj.message.chat.get('first_name', ''),
                "chat_type": payload_obj.message.chat.get('type', ''),
                "payment_date": datetime.utcfromtimestamp(payload_obj.message.date),
                "currency": successful_payment.currency,
                "total_amount": successful_payment.total_amount / 100.0, # Assuming total_amount is in cents
                "invoice_payload": successful_payment.invoice_payload,
                "telegram_payment_charge_id": successful_payment.telegram_payment_charge_id,
                "provider_payment_charge_id": successful_payment.provider_payment_charge_id
            }
            # Initialize pk_payment to None
            pk_payment = None
            # Log the successful transaction
            try:
                pk_payment = await add_payment_details(db, payment_info)
            except Exception as e:
                logger.error(f"Failed Log the successful transaction: {e}")
                

            user_credit_info = {
                "channel": "TELEGRAM",
                "pk_bot": bot_id,
                "user_id": payload_obj.message.from_.get('id'),
                "chat_id": payload_obj.message.chat.get('id'),
                "credits": credits_to_add,  # The number of credits to add
                "transaction_type": "PAYMENT",  # Indicating this is a credit transaction
                "transaction_date": datetime.utcfromtimestamp(payload_obj.message.date),  # Timestamp of the transaction
                "pk_payment": pk_payment  # Linking this credit update to the payment record
            }
            # Call the function to update user credits
            try:
                await update_user_credits(db, user_credit_info)
            except Exception as e:
                logger.error(f"Failed to update user credits: {e}")

            try:
                # After updating user credits successfully
                confirmation_text = "Thank you for your payment! 💋💋💋"
                await send_telegram_message(payload_obj.message.chat['id'], confirmation_text, bot_token)
                await send_credit_count(chat_id=chat_id, bot_token=bot_token, total_credits=await get_latest_total_credits(db=db,  user_id=user_id, bot_id=bot_id))

                logger.info(f"Payment confirmed for chat_id {payload_obj.message.chat['id']}.")
            except Exception as e:
                logger.error(f"Failed to process successful payment for chat_id {payload_obj.message.chat['id']}: {e}")

            return {"status": "Payment confirmed "}


        logger.info(f"Incoming payload is not a special case, procesing with handling of chat messages")
        # Pass the Pydantic model, chat_id, message_id, bot_id, bot_short_name, background_tasks, and db to process_message_type
        await process_message_type(payload_obj.message, chat_id, user_id, payload_obj.message.message_id, bot_id, bot_short_name, background_tasks, db, payload)


    except Exception as e:
        logger.error(f"An error occurred while processing the request: {e}")
        if chat_id:
            # Use background_tasks to add an error handling task
            background_tasks.add_task(send_error_notification, chat_id, bot_short_name, "Sorry, something went wrong. Please try again later.")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return {"status": "Message processed successfully"}

