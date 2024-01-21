# ./app/controllers/telegram_integration.py
import httpx
import logging

async def send_telegram_message(chat_id: int, text: str, bot_token: str) -> str:
    try:
        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        payload = {"chat_id": chat_id, "text": text}

        async def post_message():
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
            return response.text

        return await post_message()
    except Exception as e:
        logging.error(f"Error sending Telegram message: {str(e)}")
        return ""