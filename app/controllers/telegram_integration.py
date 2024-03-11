# ./app/controllers/telegram_integration.py
import httpx
import logging
from app.config import TELEGRAM_API_URL, STRIPE_API_KEY, CREDIT_COST_PHOTO, CREDIT_COST_AUDIO
from app.database_operations import get_latest_total_credits
from decimal import Decimal
import asyncio
import os
from typing import Tuple, List, Optional
from functools import partial

logger = logging.getLogger(__name__)

async def update_telegram_message(chat_id: int, message_id: int, new_text: str, bot_token: str) -> bool:
   """
   Updates the content of a previously sent message in Telegram.
   """
   logger.debug(f"update_telegram_message with bot_token: {bot_token}")
   url = f'{TELEGRAM_API_URL}{bot_token}/editMessageText'
   payload = {
       "chat_id": chat_id,
       "message_id": message_id,
       "text": new_text
   }

   return await send_telegram_request(url, payload)


async def send_telegram_message(chat_id: int, text: str, bot_token: str) -> Tuple[bool, int]:
   """
   Sends a text message to a user in Telegram.
   """
   logger.debug(f"send_telegram_message with bot_token: {bot_token}")
   await send_typing_action(chat_id, bot_token)

   typing_delay = calculate_typing_delay(text)
   await asyncio.sleep(typing_delay)

   url = f'{TELEGRAM_API_URL}{bot_token}/sendMessage'
   payload = {"chat_id": chat_id, "text": text}

   return await send_telegram_request(url, payload, get_message_id=True)


async def send_telegram_error_message(chat_id: int, text: str, bot_token: str) -> bool:
   logger.debug(f"send_telegram_error_message with bot_token: {bot_token}")
   url = f'{TELEGRAM_API_URL}{bot_token}/sendMessage'
   payload = {"chat_id": chat_id, "text": text}

   return await send_telegram_request(url, payload)


async def send_typing_action(chat_id: int, bot_token: str) -> bool:
   logger.debug(f"send_typing_action with bot_token: {bot_token}")
   url = f'{TELEGRAM_API_URL}{bot_token}/sendChatAction'
   payload = {"chat_id": chat_id, "action": "typing"}

   return await send_telegram_request(url, payload)


def calculate_typing_delay(message: str) -> float:
   average_typing_speed_per_minute = 200
   words = len(message.split())
   minutes_to_type = words / average_typing_speed_per_minute
   return max(0.5, minutes_to_type * 60)


async def send_audio_message(chat_id: int, audio_file_path: str, bot_token: str) -> bool:
   """
   Sends an audio message to a user in Telegram and deletes the file afterwards.
   """
   logger.debug(f"send_audio_message with bot_token: {bot_token}")
   url = f'{TELEGRAM_API_URL}{bot_token}/sendAudio'
   files = {'audio': open(audio_file_path, 'rb')}
   data = {"chat_id": chat_id}

   success = await send_telegram_request_with_file(url, files, data)

   files['audio'].close()
   try:
       os.remove(audio_file_path)
       logger.info(f"Successfully deleted audio file: {audio_file_path}")
   except Exception as e:
       logger.error(f"Failed to delete audio file: {audio_file_path}. Error: {e}")

   return success



async def send_voice_note(chat_id: int, audio_file_path: str, bot_token: str) -> bool:
    """
    Sends a voice note to a user in Telegram using a voice note stored at a local file path.
    The function also attempts to delete the voice note file after sending it.
    """
    logger.debug(f"send_voice_note with bot_token: {bot_token}")
    url = f'https://api.telegram.org/bot{bot_token}/sendVoice'

    try:
        with open(audio_file_path, 'rb') as audio_file:
            files = {
                'voice': audio_file
            }
            data = {
                'chat_id': chat_id
            }
            logger.debug(f"Sending voice note to chat_id {chat_id} with voice note from {audio_file_path}")
            success = await send_telegram_request_with_file(url, files, data)
            if success:
                logger.info(f"Voice note sent successfully to chat_id {chat_id}")
    except FileNotFoundError:
        logger.error(f"File not found: {audio_file_path}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in send_voice_note: {str(e)}")
        return False

    try:
        os.remove(audio_file_path)
        logger.info(f"Successfully deleted voice note file: {audio_file_path}")
    except Exception as e:
        logger.error(f"Failed to delete voice note file: {audio_file_path}. Error: {e}")
    
    return success

async def send_photo_message(chat_id: int, photo_temp_path: str, bot_token: str, caption: str = None) -> bool:
   """
   Sends a photo message to a user in Telegram using a photo stored at a local file path with an optional caption.
   """
   logger.debug(f"send_photo_message with bot_token: {bot_token}")
   url = f'https://api.telegram.org/bot{bot_token}/sendPhoto'

   try:
       with open(photo_temp_path, 'rb') as photo_file:
           files = {
               'photo': photo_file
           }
           data = {
               'chat_id': str(chat_id),
               'caption': caption
           }
           logger.debug(f"Sending photo message to chat_id {chat_id} with photo from {photo_temp_path} and caption '{caption}'")
           success = await send_telegram_request_with_file(url, files, data)
           if success:
               logger.info(f"Photo message sent successfully to chat_id {chat_id} with caption '{caption}'")
           return success
   except FileNotFoundError:
       logger.error(f"File not found: {photo_temp_path}")
   except Exception as e:
       logger.error(f"Unexpected error in send_photo_message: {str(e)}")
   return False



async def send_generate_options(chat_id: int, bot_token: str):
   keyboard = {
       "inline_keyboard": [
           [{"text": f"📸 See Me - (Cost {CREDIT_COST_PHOTO} Credits)", "callback_data": "generate_photo"}],
           [{"text": f"🔊 Hear Me - (Cost {CREDIT_COST_AUDIO} Credits)", "callback_data": "generate_audio"}]
       ]
   }

   text = "💕 Let's make this moment special. 💕 \n\n📸 See Me - Choose and describe your perfect photo of me. \n\n🔊 Hear Me - Pick and tell me what sweet nothings you'd like to hear."
   payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
   await send_telegram_request(f"{TELEGRAM_API_URL}{bot_token}/sendMessage", payload)


async def send_credit_count(chat_id: int, bot_token: str, total_credits: Decimal):
   keyboard = {
       "inline_keyboard": [[{"text": "Want more? 💦", "callback_data": "ask_credit"}]]
   }

   text = f"💕 You have {str(total_credits)} credits left 💕"
   payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
   await send_telegram_request(f"https://api.telegram.org/bot{bot_token}/sendMessage", payload)


async def send_credit_purchase_options(chat_id: int, bot_token: str):
   keyboard = {
       "inline_keyboard": [
           [{"text": "😈 Unlock Fun! - 100 Credits. Begin the adventure.", "callback_data": "buy_100_credits"}],
           [{"text": "🍆 Boost Power! - 500 Credits. Amplify the thrill.", "callback_data": "buy_500_credits"}],
           [{"text": "💦 Give me all! - 1000 Credits. So much to do!", "callback_data": "buy_1000_credits"}]
       ]
   }

   text = "🔥 Ignite your desires with exclusive access. Choose your pleasure:"
   payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
   await send_telegram_request(f"{TELEGRAM_API_URL}{bot_token}/sendMessage", payload)


async def send_request_for_audio(chat_id: int, bot_token: str):
    keyboard = {
        "inline_keyboard": [[{"text": "Yes, send me a voice note! 🎙️", "callback_data": "generate_audio"}]]
    }
    text = "Do you want to receive a voice note?"
    payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
    await send_telegram_request(f"https://api.telegram.org/bot{bot_token}/sendMessage", payload)

async def send_request_for_photo(chat_id: int, bot_token: str):
    keyboard = {
        "inline_keyboard": [[{"text": "Yes, show me a photo! 📸", "callback_data": "generate_photo"}]]
    }
    text = "Do you want to see a photo?"
    payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
    await send_telegram_request(f"https://api.telegram.org/bot{bot_token}/sendMessage", payload)


async def send_reset_options(chat_id: int, bot_token: str):
   keyboard = {
       "inline_keyboard": [
           [{"text": "Yes", "callback_data": "reset_yes"}],
           [{"text": "No", "callback_data": "reset_no"}]
       ]
   }

   text = "This will reset your chat history and will wipe all the bot memory. Your credits will remain. Are you sure?"
   payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
   await send_telegram_request(f"{TELEGRAM_API_URL}{bot_token}/sendMessage", payload)


async def answer_pre_checkout_query(pre_checkout_query_id: str, ok: bool, bot_token: str, error_message: str = None):
   url = f'{TELEGRAM_API_URL}{bot_token}/answerPreCheckoutQuery'
   payload = {
       "pre_checkout_query_id": pre_checkout_query_id,
       "ok": ok,
       "error_message": error_message
   }

   await send_telegram_request(url, payload)


async def send_invoice(
   chat_id: int, title: str, description: str, payload: str,
   currency: str, prices, bot_token: str, start_parameter: str = '', provider_data: str = '',
   photo_url: str = '', photo_size: int = 0, photo_width: int = 0, photo_height: int = 0,
   need_name: bool = False, need_phone_number: bool = False, need_email: bool = False,
   need_shipping_address: bool = False, send_phone_number_to_provider: bool = False,
   send_email_to_provider: bool = False, is_flexible: bool = False,
   disable_notification: bool = False, protect_content: bool = False,
   reply_markup: Optional[str] = None
) -> Tuple[bool, int]:
   """
   Sends an invoice to a user in Telegram with optional parameters included.
   """
   url = f'{TELEGRAM_API_URL}{bot_token}/sendInvoice'
   payload = {
       "chat_id": chat_id,
       "title": title,
       "description": description,
       "payload": payload,
       "provider_token": STRIPE_API_KEY,
       "currency": currency,
       "prices": prices,
       "start_parameter": start_parameter,
       "provider_data": provider_data,
       "photo_url": photo_url,
       "photo_size": photo_size,
       "photo_width": photo_width,
       "photo_height": photo_height,
       "need_name": need_name,
       "need_phone_number": need_phone_number,
       "need_email": need_email,
       "need_shipping_address": need_shipping_address,
       "send_phone_number_to_provider": send_phone_number_to_provider,
       "send_email_to_provider": send_email_to_provider,
       "is_flexible": is_flexible,
       "disable_notification": disable_notification,
       "protect_content": protect_content
   }

   if reply_markup is not None:
       payload["reply_markup"] = reply_markup

   return await send_telegram_request(url, payload, get_message_id=True)


async def send_telegram_request(url, payload, get_message_id=False):
   try:
       async with httpx.AsyncClient() as client:
           response = await client.post(url, json=payload)
           response.raise_for_status()
           if get_message_id:
               message_id = response.json().get('result', {}).get('message_id', 0)
               return True, message_id
           return True
   except httpx.HTTPStatusError as e:
       logger.error(f"HTTP error: {e}")
       logger.error(f"Request payload: {payload}")
       logger.error(f"Response content: {response.content}")
   except Exception as e:
       logger.error(f"Unexpected error: {str(e)}")
   return False, 0


async def send_telegram_request_with_file(url, files, data=None):
   try:
       async with httpx.AsyncClient() as client:
           response = await client.post(url, files=files, data=data)
           response.raise_for_status()
           return True
   except httpx.HTTPStatusError as e:
       logger.error(f"HTTP error: {e}")
   except Exception as e:
       logger.error(f"Unexpected error: {str(e)}")
   return False