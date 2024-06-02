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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from fastapi import Request, HTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from starlette.responses import PlainTextResponse
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

from app.utils.file_list_cache import get_cached_file_list

# Create a logger
logger = logging.getLogger(__name__)

MAX_PAYLOAD_SIZE_CHARS = 8 * 1024
MAX_TOKENS = 4024
MAX_ATTEMPTS = 3

limiter = Limiter(key_func=get_remote_address)

@limiter.limit("10/10 seconds")
async def send_payload_to_openrouter(api_payload: dict, request: Request) -> dict:
    try:
        #logger.debug(f"Sending payload to OpenRouter: {api_payload}")
        logger.debug(f"Sending payload to OpenRouter")
        logger.debug(f"OPENROUTER_MODEL: {OPENROUTER_MODEL}")
        async with httpx.AsyncClient() as client:
            response = await client.post(OPENROUTER_URL, json=api_payload, headers={"Authorization": f"Bearer {OPENROUTER_TOKEN}"})
        response.raise_for_status()
        logger.debug(f"Response received from OpenRouter: {response.text}")
        response_data = response.json()
        logger.debug(f"Parsed response data: {response_data}")
        if (
            isinstance(response_data, dict)
            and "choices" in response_data
            and len(response_data["choices"]) > 0
            and "message" in response_data["choices"][0]
            and "content" in response_data["choices"][0]["message"]
        ):
            logger.debug(f"Valid response format received from OpenRouter")
            return response_data
        else:
            logger.error(f"Unexpected response format from OpenRouter: {response_data}")
            return {"error": "Unexpected response format"}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == HTTP_429_TOO_MANY_REQUESTS:
            raise HTTPException(status_code=429, detail="Too Many Requests")
        else:
            logger.error(f"HTTP status error in OpenRouter request: {str(e)}")
            raise
    except httpx.RequestError as e:
        logger.error(f"Request error in OpenRouter request: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in OpenRouter request: {str(e)}")
        raise

async def rate_limit_exceeded_handler(request: Request, exc: HTTPException) -> PlainTextResponse:
    """Custom rate limit exceeded handler."""
    response = PlainTextResponse(str(exc.detail), status_code=exc.status_code)
    response.headers["Retry-After"] = "10"  # Retry after 10 seconds
    return response


async def get_chat_completion(chat_id: int, bot_id: int, request: Request, db: AsyncSession = Depends(get_db)) -> Optional[str]:
    
    assistant_prompt = await get_bot_assistant_prompt(bot_id, db)
    if not assistant_prompt:
        logger.error(f"No assistant prompt found for bot_id {bot_id}. Using default prompt.")
        return None
    
    retries = 3
    for attempt in range(retries + 1):
        try:
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

            response_data = await send_payload_to_openrouter(payload, request)

            if isinstance(response_data, dict) and response_data.get("error") == "429":
                return response_data  # Return the error response directly

            if isinstance(response_data, dict) and "error" in response_data:
                logger.error(f"Error in OpenRouter response: {response_data['error']}")
                return None

            response_text = response_data["choices"][0]["message"]["content"]
            if response_text:
                return response_text
            elif attempt < retries:
                await asyncio.sleep(60)

        except asyncio.TimeoutError:
            logger.error(f"get_chat_completion timed out for chat_id {chat_id}, attempt {attempt + 1}")
        except Exception as e:
            logger.error(f"Error in get_chat_completion: {str(e)}")
    return None

async def get_photo_filename(requested_photo: str, request: Request) -> Optional[str]:
    file_info = await get_cached_file_list()
    logger.debug(f"File info: {file_info}")
    
    list_of_files = "|".join(file_info.keys())
    logger.debug(f"List of files: {list_of_files}")

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
            logger.debug(f"Attempt {attempt}: Sending payload to OpenRouter: {payload}")
            response_data = await send_payload_to_openrouter(payload, request)
            logger.debug(f"Attempt {attempt}: Response received from OpenRouter: {response_data}")
            
            choices = response_data.get("choices", [])
            logger.debug(f"Attempt {attempt}: Choices: {choices}")
            
            if choices:
                message = choices[0].get("message", {})
                logger.debug(f"Attempt {attempt}: Message: {message}")
                
                content = message.get("content", "").strip().replace(" ", "_")
                logger.debug(f"Attempt {attempt}: Content: {content}")
                
                if content:
                    logger.debug(f"Attempt {attempt}: Received valid response")
                    return content
                else:
                    logger.warning(f"Attempt {attempt}: Received empty content. Retrying...")
            else:
                logger.warning(f"Attempt {attempt}: No choices in response. Retrying...")
            
            await asyncio.sleep(1)

        except HTTPError:
            return None
    
    logger.error("Failed to receive a valid response after maximum attempts.")
    return None

async def construct_photo_finder_prompt(requested_photo: str, file_list: str) -> str:
    """Constructs and returns a prompt string for the photo finder."""
    logger.debug(f"Requested photo: {requested_photo}")
    logger.debug(f"File list: {file_list}")

    prompt = (
        "###Instruction###\n"
        "You are the most advanced photo selection AI, specialized in matching descriptive texts with the most suitable file names from a given list. Your task is to analyze a description and identify the file name that best corresponds to it. Precision and attention to detail are paramount.\n\n"
        "###Task Instructions###\n"
        "1. Understand the Description: Carefully read the user-requested photo description. Pay attention to key descriptors (e.g., colors, objects, settings).\n"
        "2. Analyze the List of Files: Review each file name in the provided list. Consider how elements of each file name might relate to the description's details.\n"
        "3. Match Description to File Names: Select the file name that best aligns with the description. If the description matches multiple files, order them by relevance, from the highest to the lowest match.\n"
        "4. Handling Ambiguities: If no file perfectly matches but multiple could fit based on some description aspects, list them by their degree of relevance. If no file closely matches, choose the one that is most loosely related.\n"
        "5. Response Format: Your response should consist solely of the file name(s), exactly as listed, without any additional text or explanation. Separate multiple file names with a semicolon.\n\n"
        "###Question###\n"
        f"Description: {requested_photo}\n"
        f"List of Files:\n{file_list}\n\n"
        "###Important Notes###\n"
        "- Precision in matching the description to the file names is crucial. Always strive for the most accurate match.\n"
        "- Always return at least one file name, even if the match is not perfect. Choose the closest option available.\n"
        "- Your response must include the exact file name as it is essential for subsequent processes.\n\n"
        "###Your Task###\n"
        "You MUST analyze the description and the list of files, then provide the most suitable file name(s) based on the given criteria. Ensure that your answer is unbiased and avoids relying on stereotypes.\n\n"
        "###Response Primer###\n"
        "Your response should be the file name(s) perfectly written as it will be input in another function. Separate multiple file names with a semicolon.\n"
    )

    return prompt


async def generate_photo_reaction(photo_caption: str, file_name: str, bot_id: int, request: Request, db: AsyncSession) -> str:
    """Generate a reaction to a given photo caption and file name."""

    try:
        assistant_prompt = await get_bot_assistant_prompt(bot_id, db)
        logger.debug(f"assistant_prompt: {assistant_prompt}")

        logger.debug(f"reaction to caption: {photo_caption} filename {file_name}")
        payload = {
            "model": OPENROUTER_MODEL,
            "max_tokens": MAX_TOKENS,
            "temperature": 1,  # Encourages predictability with minimal variability
            "top_p": 1,  # Keeps a broad token choice
            "frequency_penalty": 0.7,  # Discourages frequent token repetition
            "repetition_penalty": 1,  # Prevents input token repetition
            "messages": [{
                "role": "system",
                "content": f"{assistant_prompt} FIRSTS TASKS: [SYSTEM MSG: REPLY SHORT MAX 50 CHARACTERS] React to this photo of yours caption: '{photo_caption}' and its file name: '{file_name}',  be creative, dont put the caption or the filename just say what you think about it staying in the character [SYSTEM MSG: REPLY SHORT MAX 50 CHARACTERS]"
            }]
        }
        response_data = await send_payload_to_openrouter(payload, request)
        reaction = response_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        
        logger.debug(f"reaction response: {reaction}")
        return reaction
    except Exception as e:
        logger.error(f"Error generating photo reaction: {e}")
        return "Sorry, I couldn't generate a reaction for the photo."
