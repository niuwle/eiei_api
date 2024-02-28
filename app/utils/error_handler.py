# app/routers/error_handler.py
from functools import wraps
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
                background_tasks.add_task(send_error_message_to_user, chat_id, bot_short_name, "Sorry, something went wrong. Please try again later.")
            # Re-raise the exception to let FastAPI's global exception handler take over
            raise
    return wrapper
