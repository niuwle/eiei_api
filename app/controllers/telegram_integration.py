# ./app/controllers/telegram_integration.py
import httpx
import logging
from app.config import TELEGRAM_API_URL
import asyncio
import os 

logger = logging.getLogger(__name__)

async def send_telegram_message(chat_id: int, text: str, bot_token: str) -> bool:
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

async def send_photo_message(chat_id: int, photo_url: str, bot_token: str) -> bool:
    """
    Sends a photo message to a user in Telegram using the photo's URL.

    Parameters:
    - chat_id (int): The chat ID to send the photo message to.
    - photo_url (str): The URL of the photo to be sent.
    - bot_token (str): The Telegram bot token.

    Returns:
    - bool: True if the message was sent successfully, False otherwise.
    """
    url = f'{TELEGRAM_API_URL}{bot_token}/sendPhoto'
    payload = {"chat_id": chat_id, "photo": photo_url}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload)
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error sending photo message: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in send_photo_message: {str(e)}")
    return False
