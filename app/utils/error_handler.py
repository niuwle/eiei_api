# app/utils/error_handler.py
from functools import wraps
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.controllers.telegram_integration import send_telegram_error_message
from sqlalchemy.ext.asyncio import AsyncSession
import logging
app = FastAPI()

logger = logging.getLogger(__name__)

def error_handler(endpoint):
    """
    A decorator to wrap around endpoint functions to catch exceptions,
    log them, and send an error message to the user.
    """
    @wraps(endpoint)
    async def wrapper(*args, **kwargs):
        request: Request = kwargs.get('request')
        background_tasks: BackgroundTasks = kwargs.get('background_tasks')
        bot_short_name: str = kwargs.get('bot_short_name')
        try:
            # Attempt to extract chat_id from the request body for error reporting
            body = await request.json()
            chat_id = body.get('message', {}).get('chat', {}).get('id') if body.get('message') else None
        except:
            chat_id = None
        try:
            return await endpoint(*args, **kwargs)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            if chat_id:
                # If we have a chat_id, attempt to notify the user of the error
                background_tasks.add_task(send_telegram_error_message, chat_id, "Sorry, something went wrong. Please try again later. e003",  bot_short_name)
            # Re-raise the exception to let FastAPI's global exception handler take over
            raise
    return wrapper


async def send_error_notification(chat_id: int, bot_short_name: str, error_message: str = "Sorry, something went wrong. Please try again later."):
    try:
        
        await send_telegram_error_message(chat_id, error_message, bot_short_name)
    except Exception as e:
        logger.error(f"Failed to send error notification to user: {e}")
