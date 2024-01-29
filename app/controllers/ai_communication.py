# ./app/controllers/ai_communication.py
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import logging
from app.models.message import tbl_msg
from typing import Optional
from app.config import OPENROUTER_TOKEN, OPENROUTER_MODEL, OPENROUTER_URL, ASSISTANT_PROMPT
from httpx import HTTPError
from sqlalchemy.future import select

# Create a logger
logger = logging.getLogger(__name__)

async def get_chat_completion(chat_id: int, bot_id: int, db: AsyncSession) -> Optional[str]:
    try:
        messages = await db.execute(select(tbl_msg).filter(tbl_msg.chat_id == chat_id, tbl_msg.bot_id == bot_id).order_by(tbl_msg.message_date))
        messages = messages.scalars().all()
        logger.info(f"Retrieved {len(messages)} messages for chat_id {chat_id} and bot_id {bot_id}")
        # Calculate initial payload size
        payload_size = len(str([{"role": "system", "content": ASSISTANT_PROMPT}] + [{"role": message.role.lower(), "content": message.content_text} for message in messages]))

        # Remove oldest messages if payload size exceeds 8k  characters
        while payload_size > 8 * 1024:
            oldest_message = messages.pop(0)
            payload_size -= len(str({"role": oldest_message.role.lower(), "content": oldest_message.content_text}))

        payload = {
            "model": OPENROUTER_MODEL,
            "max_tokens": 4024,
            "messages": [{"role": "system", "content": ASSISTANT_PROMPT}] + [{"role": message.role.lower(), "content": message.content_text} for message in messages]
        }

        logger.debug(f"Sending JSON payload to OpenRouter: {payload}")  # Log the sent JSON payload

        async def fetch_response():
            async with httpx.AsyncClient() as client:
                response = await client.post(OPENROUTER_URL, json=payload, headers={"Authorization": f"Bearer {OPENROUTER_TOKEN}"})
            return response.json()

        response_data = await fetch_response()
        logger.info(f"Received response from OpenRouter: {response_data}")  # Log the received response

        return response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

    except HTTPError as e:
        logger.error(f"HTTP error in get_chat_completion: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_chat_completion: {str(e)}")
        return None
