# ./app/controllers/telegram_integration.py
import httpx
import logging
from app.config import TELEGRAM_API_URL

logger = logging.getLogger(__name__)

async def send_telegram_message(chat_id: int, text: str, bot_token: str) -> bool:
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
