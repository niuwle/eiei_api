# ./app/controllers/telegram_integration.py
import httpx
import logging
import asyncio
import os
from app.config import TELEGRAM_API_URL

logger = logging.getLogger(__name__)

async def send_request(url: str, payload: dict, method: str = "post", files: dict = None) -> bool:
    try:
        async with httpx.AsyncClient() as client:
            if method == "post" and files:
                response = await client.post(url, files=files, data=payload)
            else:
                response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.debug(f"Request to {url} successful.")
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for {url}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error for {url}: {str(e)}")
    return False

async def update_telegram_message(chat_id: int, message_id: int, new_text: str, bot_token: str) -> bool:
    url = f'{TELEGRAM_API_URL}{bot_token}/editMessageText'
    payload = {"chat_id": chat_id, "message_id": message_id, "text": new_text}
    return await send_request(url, payload)

async def send_telegram_message(chat_id: int, text: str, bot_token: str) -> [bool, int]:
    await send_typing_action(chat_id, bot_token)
    typing_delay = calculate_typing_delay(text)
    await asyncio.sleep(typing_delay)
    url = f'{TELEGRAM_API_URL}{bot_token}/sendMessage'
    payload = {"chat_id": chat_id, "text": text}
    result = await send_request(url, payload)
    return result is not False, result.get('result', {}).get('message_id', 0) if result else 0

async def send_typing_action(chat_id: int, bot_token: str) -> bool:
    url = f'{TELEGRAM_API_URL}{bot_token}/sendChatAction'
    payload = {"chat_id": chat_id, "action": "typing"}
    return await send_request(url, payload)

def calculate_typing_delay(message: str) -> float:
    words = len(message.split())
    return max(0.5, words / 200 * 60)  # 200 wpm, minimum 0.5s delay

async def send_media_message(chat_id: int, file_path: str, bot_token: str, message_type: str) -> bool:
    url = f'{TELEGRAM_API_URL}{bot_token}/send{message_type.capitalize()}'
    files = {message_type: open(file_path, 'rb')}
    payload = {"chat_id": chat_id}
    result = await send_request(url, payload, files=files)
    if files[message_type]:
        files[message_type].close()
        os.remove(file_path)
        logger.info(f"{message_type.capitalize()} file {file_path} deleted successfully.")
    return result is not False

async def send_audio_message(chat_id: int, audio_file_path: str, bot_token: str) -> bool:
    return await send_media_message(chat_id, audio_file_path, bot_token, "audio")

async def send_voice_note(chat_id: int, audio_file_path: str, bot_token: str) -> bool:
    return await send_media_message(chat_id, audio_file_path, bot_token, "voice")

async def send_photo_message(chat_id: int, photo_url: str, bot_token: str) -> bool:
    url = f'{TELEGRAM_API_URL}{bot_token}/sendPhoto'
    payload = {"chat_id": chat_id, "photo": photo_url}
    return await send_request(url, payload) is not False
