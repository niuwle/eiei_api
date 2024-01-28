# ./app/controllers/telegram_integration.py
import httpx
import logging
from app.config import TELEGRAM_API_URL
import asyncio

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
