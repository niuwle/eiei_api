# app/utils/error_handler.py
from functools import wraps
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.controllers.telegram_integration import send_telegram_message
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_operations import get_bot_id_by_short_name
app = FastAPI()

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
        bot_id = await get_bot_id_by_short_name(bot_short_name, db)
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
                background_tasks.add_task(send_error_notification, chat_id, bot_id, "Sorry, something went wrong. Please try again later.")
            # Re-raise the exception to let FastAPI's global exception handler take over
            raise
    return wrapper


async def send_error_notification(chat_id: int, bot_id: int, db: AsyncSession, error_message: str = "Sorry, something went wrong. Please try again later."):
    try:
        
        await send_telegram_message(chat_id, error_message, bot_token)
    except Exception as e:
        logger.error(f"Failed to send error notification to user: {e}")
