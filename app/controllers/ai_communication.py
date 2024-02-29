# ./app/controllers/ai_communication.py
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import logging
from app.models.message import tbl_msg
from typing import Optional
from app.config import OPENROUTER_TOKEN, OPENROUTER_MODEL, OPENROUTER_URL
from httpx import HTTPError
from sqlalchemy.future import select
from app.database_operations import get_bot_assistant_prompt 

from app.utils.file_list_cache import get_cached_file_list
# Create a logger
logger = logging.getLogger(__name__)

async def get_chat_completion(chat_id: int, bot_id: int, db: AsyncSession) -> Optional[str]:
    try:
        # Fetch the assistant prompt for the specific bot_id
        assistant_prompt = await get_bot_assistant_prompt(bot_id, db)
        if not assistant_prompt:
            logger.error(f"No assistant prompt found for bot_id {bot_id}. Using default prompt.")
            return None

        messages = await db.execute(select(tbl_msg).filter(tbl_msg.chat_id == chat_id, tbl_msg.bot_id == bot_id, tbl_msg.is_processed != 'S', tbl_msg.is_reset != 'Y').order_by(tbl_msg.message_date))
        messages = messages.scalars().all()
        logger.info(f"Retrieved {len(messages)} messages for chat_id {chat_id} and bot_id {bot_id}")
        # Calculate initial payload size
        payload_size = len(str([{"role": "system", "content": assistant_prompt}] + [{"role": message.role.lower(), "content": message.content_text} for message in messages]))

        # Remove oldest messages if payload size exceeds 8k characters
        while payload_size > 8 * 1024:
            oldest_message = messages.pop(0)
            payload_size -= len(str({"role": oldest_message.role.lower(), "content": oldest_message.content_text}))

        payload = {
            "model": OPENROUTER_MODEL,
            "max_tokens": 4024,
            "messages": [{"role": "system", "content": assistant_prompt}] + [{"role": message.role.lower(), "content": message.content_text} for message in messages]
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


async def get_photo_filename(requested_photo: str):
    # Refresh the file list cache when needed
    file_info = await get_cached_file_list()

    # Generate a bullet-point list of file names
    # Assuming file_info is a dict mapping file names to URLs, we list the file names
    list_of_files = "\n".join([f"• {file_name}" for file_name in file_info.keys()])

    # Construct the prompt with better formatting
    get_photo_filename_prompt = (
        "You are the best photo picker based on a description software in the world.\n"
        "Task: Given a list of file names and a descriptive text, find the file name that best matches the description. "
        "Return only the exact file name that matches the description.\n"
        "Description: {}\n"
        "List of Files:\n{}\n"
        "Select the file name that best matches the description above. "
        "If more than one could match, order by best match and separate files by semicolon. "
        "If no match at all then reply with the most closest option, always return at least one filename.\n"
        "Example:\n"
        "user: Show me a photo of a red car\n"
        "Response: red_sports_car.jpg\n\n"
        "Example:\n"
        "user: i like to see nature\n"
        "Response: yellow_sunflower_field.bmp;sunset_over_mountains.jpg"
    ).format(requested_photo, list_of_files)

    try:
        payload = {
            "model": OPENROUTER_MODEL,
            "max_tokens": 4024,
            "messages": [{"role": "system", "content": get_photo_filename_prompt}]
        }

        logger.debug(f"Sending JSON payload to OpenRouter: {payload}")

        async with httpx.AsyncClient() as client:
            response = await client.post(OPENROUTER_URL, json=payload, headers={"Authorization": f"Bearer {OPENROUTER_TOKEN}"})
        response_data = response.json()

        logger.info(f"Received response from OpenRouter: {response_data}")

        return response_data.get("choices", [{}])[0].get("message", {}).get("content", "").replace("•", "").strip()


    except HTTPError as e:
        logger.error(f"HTTP error in get_photo_filename: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_photo_filename: {str(e)}")
        return None

