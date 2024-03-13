# ./app/controllers/ai_communication.py
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import logging
import asyncio
from app.models.message import tbl_msg
from typing import Optional
from app.config import OPENROUTER_TOKEN, OPENROUTER_MODEL, OPENROUTER_URL
from httpx import HTTPError
from sqlalchemy.future import select
from app.database_operations import get_bot_assistant_prompt 

from app.utils.file_list_cache import get_cached_file_list
# Create a logger
logger = logging.getLogger(__name__)

MAX_PAYLOAD_SIZE_CHARS = 8 * 1024
MAX_TOKENS = 4024
MAX_ATTEMPTS = 3

async def send_payload_to_openrouter(api_payload: dict) -> dict:
    """Helper function to send payload to OpenRouter and return the response."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OPENROUTER_URL, json=api_payload, headers={"Authorization": f"Bearer {OPENROUTER_TOKEN}"})
        response.raise_for_status()
        logger.debug(f"Payload sent to OpenRouter: {api_payload}")
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP status error in OpenRouter request: {str(e)}")
        raise
    except httpx.RequestError as e:
        logger.error(f"Request error in OpenRouter request: {str(e)}")
        raise

async def get_chat_completion(chat_id: int, bot_id: int, db: AsyncSession) -> Optional[str]:
    retries = 3
    for attempt in range(retries + 1):
        try:
            assistant_prompt = await get_bot_assistant_prompt(bot_id, db)
            if not assistant_prompt:
                logger.error(f"No assistant prompt found for bot_id {bot_id}. Using default prompt.")
                return None

            messages = await db.execute(select(tbl_msg).filter(tbl_msg.chat_id == chat_id, tbl_msg.bot_id == bot_id, tbl_msg.is_processed != 'S', tbl_msg.is_reset != 'Y').order_by(tbl_msg.message_date))
            messages = messages.scalars().all()

            while len(str(messages)) > MAX_PAYLOAD_SIZE_CHARS:
                messages.pop(0)

            payload = {
                "model": OPENROUTER_MODEL,
                "max_tokens": MAX_TOKENS,
                "temperature": 0.9,  # Encourages predictability with minimal variability
                "top_p": 1,  # Keeps a broad token choice
                "frequency_penalty": 0.7,  # Discourages frequent token repetition
                "repetition_penalty": 1,  # Prevents input token repetition
                "messages": [{"role": "system", "content": assistant_prompt}] + [{"role": message.role.lower(), "content": message.content_text} for message in messages]
            }

            response_data = await send_payload_to_openrouter(payload)

            response_text = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if response_text:
                return response_text
            elif attempt < retries:
                await asyncio.sleep(2)
        except asyncio.TimeoutError:
            logger.error(f"get_chat_completion timed out for chat_id {chat_id}, attempt {attempt + 1}")
        except Exception as e:
            logger.error(f"Error in get_chat_completion: {str(e)}")
    return None


async def get_photo_filename(requested_photo: str) -> Optional[str]:
    file_info = await get_cached_file_list()
    list_of_files = "|".join(file_info.keys())

    payload = {
        "model": OPENROUTER_MODEL,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.9,  # Encourages predictability with minimal variability
        "top_p": 1,  # Keeps a broad token choice
        "frequency_penalty": 0.7,  # Discourages frequent token repetition
        "repetition_penalty": 1,  # Prevents input token repetition
        "messages": [{"role": "system", "content": await construct_photo_finder_prompt(requested_photo, list_of_files)}]
    }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response_data = await send_payload_to_openrouter(payload)
            response_content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip().replace(" ", "_")

            if response_content:
                logger.debug(f"Attempt {attempt}: Received valid response")
                return response_content
            else:
                logger.warning(f"Attempt {attempt}: Received empty response. Retrying...")
                await asyncio.sleep(1)

        except HTTPError:
            return None
    logger.error("Failed to receive a valid response after maximum attempts.")
    return None

async def construct_photo_finder_prompt(requested_photo: str, file_list: str) -> str:
   """Constructs and returns a prompt string for the photo finder."""
   prompt = (
      "You are the most advanced photo selection AI, specialized in matching descriptive texts with the most suitable file names from a given list. "
      "Your task is to analyze a description and identify the file name that best corresponds to it. Precision and attention to detail are paramount.\n"
      "\nTask Instructions:\n"
      "1. Understand the Description: Carefully read the user-requested photo description. Pay attention to key descriptors (e.g., colors, objects, settings).\n"
      "2. Analyze the List of Files: Review each file name in the provided list. Consider how elements of each file name might relate to the description's details.\n"
      "3. Match Description to File Names: Select the file name that best aligns with the description. If the description matches multiple files, order them by relevance, from the highest to the lowest match.\n"
      "4. Handling Ambiguities: If no file perfectly matches but multiple could fit based on some description aspects, list them by their degree of relevance. If no file closely matches, choose the one that is most loosely related.\n"
      "5. Response Format: Your response should consist solely of the file name(s), exactly as listed, without any additional text or explanation. Separate multiple file names with a semicolon.\n"
      f"Description: {requested_photo}\n"
      f"List of Files:\n{file_list}\n"
      "Select the file name that best matches the description above. "
      "If more than one could match, order by best match and separate files by semicolon. "
      "If no match at all then reply with the most closest option, always return at least one filename.\n"
      "YOUR RESPONSE SHOULD ONLY BE THE FILENAME, NOTHING ELSE, THE FILE NAME PERFECTLY WRITTEN AS IT WILL BE INPUT IN ANOTHER FUNCTION.\n"
      "\nImportant Notes:\n"
      "- Precision in matching the description to the file names is crucial. Always strive for the most accurate match.\n"
      "- Always return at least one file name, even if the match is not perfect. Choose the closest option available.\n"
      "- Your response must include the exact file name as it is essential for subsequent processes."
   )

   return prompt


async def generate_photo_reaction(photo_caption: str, file_name: str, bot_id: int, db: AsyncSession) -> str:
    """Generate a reaction to a given photo caption and file name."""

    assistant_prompt = await get_bot_assistant_prompt(bot_id, db)

    logger.debug(f"reaction to caption: {photo_caption} filename {file_name}")
    payload = {
        "model": OPENROUTER_MODEL,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.9,  # Encourages predictability with minimal variability
        "top_p": 1,  # Keeps a broad token choice
        "frequency_penalty": 0.7,  # Discourages frequent token repetition
        "repetition_penalty": 1,  # Prevents input token repetition
        "messages": [{
            "role": "system",
            "content": f"{assistant_prompt} Your first task is react to this photo caption '{photo_caption}' and its file name '{file_name}',  be creative"
        }]
    }
    response_data = await send_payload_to_openrouter(payload)
    reaction = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    
    logger.debug(f"reaction response: {reaction}")
    return reaction
