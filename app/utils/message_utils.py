import logging

from app.controllers.telegram_integration import send_telegram_message
from app.database import get_db
from app.database_operations import get_bot_id_by_short_name, get_bot_token

logger = logging.getLogger(__name__)

async def send_error_message_to_user(chat_id: int, bot_short_name: str, message: str):
    try:
        async with get_db() as db:
            bot_id = await get_bot_id_by_short_name(bot_short_name, db)
            bot_token = await get_bot_token(bot_id, db)
            await send_telegram_message(chat_id, message, bot_token)
    except Exception as e:
        logger.error(f"Failed to send error message to user due to: {e}")
