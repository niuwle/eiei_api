# app/utils/error_handler.py
from fastapi import HTTPException
import logging
from app.database import get_db
from app.database_operations import get_bot_token
from app.controllers.telegram_integration import send_telegram_message

logger = logging.getLogger(__name__)

async def handle_exception(e, chat_id=None, bot_short_name=None, status_code=500, detail="An unexpected error occurred"):
    logger.error(f"Unexpected error: {str(e)}")
    if chat_id and bot_short_name:
        try:
            async with get_db() as db:
                bot_id = await get_bot_id_by_short_name(bot_short_name, db)
                bot_token = await get_bot_token(bot_id, db)
                error_message = "Sorry, something went wrong. Please try again later. "
                await send_telegram_message(chat_id, error_message+detail, bot_token)
                return {"pk_messages": added_message.pk_messages, "status": error_message+detail}
        except Exception as send_error:
            logger.error(f"Failed to send error message to user: {send_error}")
    raise HTTPException(status_code=status_code, detail=detail)
