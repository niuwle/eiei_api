import asyncio
import httpx
from datetime import datetime
from app.config import TELEGRAM_SECRET_TOKEN, HOST_URL
from app.database_operations import get_users_for_auto_reply
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

# Assuming SQLALCHEMY_DATABASE_URL is your database connection string
from app.config import SQLALCHEMY_DATABASE_URL

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def check_and_trigger_responses():
    while True:
        logger.debug("Checking automatic replies")
        async with AsyncSessionLocal() as db:
            users = await get_users_for_auto_reply(db)
            logger.debug(f'users automatic replies: {users}')
            for chat_id, user_id, bot_short_name in users:  # Unpack the tuple directly
                payload = {
                    "update_id": -1,
                    "message": {
                        "message_id": -1,
                        "from": {"id": user_id},  # Access by unpacked value
                        "chat": {"id": chat_id},  # Access by unpacked value
                        "date": int(datetime.now().timestamp()),
                        "text": "[SYSTEM MEESAGE] Please send a reply to the user based on your previous conversation that will get him excited to continue chatting with you",
                    }
                }
                # Ensure you're using the correct variable for the bot short name
                url = f'{HOST_URL}/telegram-webhook/{TELEGRAM_SECRET_TOKEN}/{bot_short_name}'  # Use bot_short_name directly
                async with httpx.AsyncClient() as client:
                    await client.post(url, json=payload)

            logger.debug("Ended automatic replies")
            await asyncio.sleep(14400)
