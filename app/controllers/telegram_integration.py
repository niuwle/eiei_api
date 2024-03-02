# ./app/controllers/telegram_integration.py
import httpx
import logging
from app.config import TELEGRAM_API_URL, STRIPE_API_KEY
from app.database_operations import get_latest_total_credits
from decimal import Decimal
import asyncio
import os 
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

async def update_telegram_message(chat_id: int, message_id: int, new_text: str, bot_token: str) -> bool:
    """
    Updates the content of a previously sent message in Telegram.

    Parameters:
    - chat_id (int): The chat ID where the message was sent.
    - message_id (int): The ID of the message to update.
    - new_text (str): The new text content for the message.
    - bot_token (str): The Telegram bot token.

    Returns:
    - bool: True if the message content was updated successfully, False otherwise.
    """
    url = f'{TELEGRAM_API_URL}{bot_token}/editMessageText'
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": new_text
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error updating message content: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in update_message_content: {str(e)}")
    return False


async def send_telegram_message(chat_id: int, text: str, bot_token: str) -> Tuple[bool, int]:
    """
    Sends a text message to a user in Telegram.

    Parameters:
    - chat_id (int): The chat ID to send the message to.
    - text (str): The text of the message to be sent.
    - bot_token (str): The Telegram bot token.

    Returns:
    - Tuple[bool, int]: A tuple containing a boolean indicating if the message was sent successfully and the message ID.
    """
    # Send 'typing' action
    await send_typing_action(chat_id, bot_token)

    # Calculate delay based on the length of the message
    typing_delay = calculate_typing_delay(text)
    await asyncio.sleep(typing_delay)

    # Send the actual message
    url = f'{TELEGRAM_API_URL}{bot_token}/sendMessage'
    payload = {"chat_id": chat_id, "text": text}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            message_id = response.json().get('result', {}).get('message_id', 0)
            return True, message_id
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending Telegram message: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in send_telegram_message: {str(e)}")
    return False, 0


async def send_telegram_error_message(chat_id: int, text: str, bot_token: str) -> bool:
    
    url = f'{TELEGRAM_API_URL}{bot_token}/sendMessage'
    payload = {"chat_id": chat_id, "text": text}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending Telegram message: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in send_telegram_message: {str(e)}")
    return False

async def send_typing_action(chat_id: int, bot_token: str) -> bool:
    url = f'{TELEGRAM_API_URL}{bot_token}/sendChatAction'
    payload = {"chat_id": chat_id, "action": "typing"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending typing action: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in send_typing_action: {str(e)}")
    return False


def calculate_typing_delay(message: str) -> float:
    average_typing_speed_per_minute = 200  # average words per minute (wpm)
    words = len(message.split())
    minutes_to_type = words / average_typing_speed_per_minute
    return max(0.5, minutes_to_type * 60)  # Minimum delay of 0.5 seconds


async def send_audio_message(chat_id: int, audio_file_path: str, bot_token: str) -> bool:
    """
    Sends an audio message to a user in Telegram and deletes the file afterwards.

    Parameters:
    - chat_id (int): The chat ID to send the audio message to.
    - audio_file_path (str): The file path to the audio file to be sent.
    - bot_token (str): The Telegram bot token.

    Returns:
    - bool: True if the message was sent successfully, False otherwise.
    """
    url = f'{TELEGRAM_API_URL}{bot_token}/sendAudio'
    files = {'audio': open(audio_file_path, 'rb')}

    data = {"chat_id": chat_id}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files, data=data)
        response.raise_for_status()
        success = True
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending audio message: {e}")
        success = False
    except Exception as e:
        logger.error(f"Unexpected error in send_audio_message: {str(e)}")
        success = False
    finally:
        files['audio'].close()
        try:
            os.remove(audio_file_path)  # Delete the file after sending
            logger.info(f"Successfully deleted audio file: {audio_file_path}")
        except Exception as e:
            logger.error(f"Failed to delete audio file: {audio_file_path}. Error: {e}")

    return success

async def send_voice_note(chat_id: int, audio_file_path: str, bot_token: str) -> bool:
    """
    Sends a voice note to a user in Telegram and deletes the file afterwards.

    Parameters:
    - chat_id (int): The chat ID to send the voice note to.
    - audio_file_path (str): The file path to the audio file to be sent.
    - bot_token (str): The Telegram bot token.

    Returns:
    - bool: True if the voice note was sent successfully, False otherwise.
    """
    url = f'{TELEGRAM_API_URL}{bot_token}/sendVoice'
    files = {'voice': open(audio_file_path, 'rb')}

    data = {"chat_id": chat_id}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files, data=data)
        response.raise_for_status()
        success = True
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending voice note: {e}")
        success = False
    except Exception as e:
        logger.error(f"Unexpected error in send_voice_note: {str(e)}")
        success = False
    finally:
        files['voice'].close()
        try:
            os.remove(audio_file_path)  # Delete the file after sending
            logger.info(f"Successfully deleted voice note file: {audio_file_path}")
        except Exception as e:
            logger.error(f"Failed to delete voice note file: {audio_file_path}. Error: {e}")

    return success

async def send_photo_message(chat_id: int, photo_temp_path: str, bot_token: str) -> bool:
    """
    Sends a photo message to a user in Telegram using a photo stored at a local file path.

    Parameters:
    - chat_id (int): The chat ID to send the photo message to.
    - photo_temp_path (str): The file system path to the photo to be sent.
    - bot_token (str): The Telegram bot token.

    Returns:
    - bool: True if the message was sent successfully, False otherwise.
    """
    url = f'https://api.telegram.org/bot{bot_token}/sendPhoto'

    # Ensure the file at the path exists and can be opened
    try:
        with open(photo_temp_path, 'rb') as photo_file:
            files = {
                'photo': photo_file,
                'chat_id': (None, str(chat_id))
            }
            logger.debug(f"Sending photo message to chat_id {chat_id} with photo from {photo_temp_path}")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, files=files)
            response.raise_for_status()

            logger.info(f"Photo message sent successfully to chat_id {chat_id}. Response: {response.json()}")
            return True
    except FileNotFoundError:
        logger.error(f"File not found: {photo_temp_path}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending photo message: {e}. Response: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error in send_photo_message: {str(e)}")
    return False

async def send_generate_options(chat_id: int, bot_token: str):
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "📸 See Me - Choose and describe your perfect photo of me.", "callback_data": "generate_photo"}],
            [{"text": "🔊 Hear Me - Pick and tell me what sweet nothings you'd like to hear.", "callback_data": "generate_audio"}]
        ]
    }
    text = "💕 Let's make this moment special. 💕"
    payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
    url = f"{TELEGRAM_API_URL}{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)


async def send_credit_count(chat_id: int, bot_token: str, total_credits: Decimal) :
    keyboard = {
        "inline_keyboard": [[{"text": "Want more? 💦", "callback_data": "ask_credit"}]]
    } 
    
    text = f"💕 You have {str(total_credits)} credits left 💕"  # Convert Decimal to str for formatting
    payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def send_credit_purchase_options(chat_id: int, bot_token: str):
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "😈 Unlock Fun! - 100 Credits. Begin the adventure.", "callback_data": "buy_100_credits"}],
            [{"text": "🍆 Boost Power! - 500 Credits. Amplify the thrill.", "callback_data": "buy_500_credits"}],
            [{"text": "💦 Give me all! - 1000 Credits. So much to do!", "callback_data": "buy_1000_credits"}]
        ]
    }
    
    text = ("🔥 Ignite your desires with exclusive access. Choose your pleasure:")
    
    # Payload for the sendMessage request with the inline keyboard
    payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
    
    # API endpoint URL
    url = f"{TELEGRAM_API_URL}{bot_token}/sendMessage"
    
    # Sending the message with the inline keyboard to the user
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        
        # Optional: Check response status and handle potential errors
        if response.status_code != 200:
            logger.error(f"Failed to send credit purchase options. Response: {response.text}")

async def send_reset_options(chat_id: int, bot_token: str):
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "Yes", "callback_data": "reset_yes"}],
            [{"text": "No", "callback_data": ""}]
        ]
    }
    
    text = ("This will reset your chat history and will wipe all the bot memory. Your credits will remain. Are you sure?")
    
    # Payload for the sendMessage request with the inline keyboard
    payload = {"chat_id": chat_id, "text": text, "reply_markup": keyboard}
    
    # API endpoint URL
    url = f"{TELEGRAM_API_URL}{bot_token}/sendMessage"
    
    # Sending the message with the inline keyboard to the user
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        
        # Optional: Check response status and handle potential errors
        if response.status_code != 200:
            logger.error(f"Failed to send credit purchase options. Response: {response.text}")

async def answer_pre_checkout_query(pre_checkout_query_id: str, ok: bool, bot_token: str, error_message: str = None):
    url = f'{TELEGRAM_API_URL}{bot_token}/answerPreCheckoutQuery'
    payload = {
        "pre_checkout_query_id": pre_checkout_query_id,
        "ok": ok,
        "error_message": error_message
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to send PreCheckoutQuery response: {response.text}")

async def send_invoice(
    chat_id: int, title: str, description: str, payload: str,
    currency: str, prices, bot_token: str, start_parameter: str = '', provider_data: str = '',  
    photo_url: str = '', photo_size: int =  0, photo_width: int =  0, photo_height: int =  0,  
    need_name: bool = False, need_phone_number: bool = False, need_email: bool = False,  
    need_shipping_address: bool = False, send_phone_number_to_provider: bool = False,  
    send_email_to_provider: bool = False, is_flexible: bool = False,  
    disable_notification: bool = False, protect_content: bool = False,  
    reply_markup: Optional[str] = None  # Expect a serialized JSON string or None
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

    # Add reply_markup to the payload only if it's not None
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            message_id = response.json().get('result', {}).get('message_id',  0)
            return True, message_id
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending invoice: {e}")
        # Additional logging for debugging
        logger.error(f"Request payload: {payload}")
        logger.error(f"Response content: {response.content}")
        return False,  0
    except Exception as e:
        logger.error(f"Unexpected error in send_invoice: {str(e)}")
        return False,  0
