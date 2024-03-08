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
        logger.debug("Starting to check for users eligible for automatic replies.")
        async with AsyncSessionLocal() as db:
            users = await get_users_for_auto_reply(db)
            if users:
                logger.info(f"Identified {len(users)} users for automatic replies: {users}")
            else:
                logger.info("No users identified for automatic replies at this time.")

            for chat_id, user_id, bot_short_name in users:
                payload = {
                    "update_id": -1,
                    "message": {
                        "message_id": -1,
                        "from": {"id": user_id},
                        "chat": {"id": chat_id},
                        "date": int(datetime.utcnow().timestamp()),
                        "text": "[SYSTEM MESSAGE] Please send a reply to the user based on your previous conversation that will get him excited to continue chatting with you",
                    }
                }
                url = f'{HOST_URL}/telegram-webhook/{TELEGRAM_SECRET_TOKEN}/{bot_short_name}'
                
                logger.info(f"Sending automatic reply to user_id: {user_id}, chat_id: {chat_id}, via bot: {bot_short_name}")
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload)
                    if response.status_code == 200:
                        logger.info(f"Successfully sent automatic reply to user_id: {user_id}, chat_id: {chat_id}")
                    else:
                        logger.error(f"Failed to send automatic reply to user_id: {user_id}, chat_id: {chat_id}. Response status: {response.status_code}")

            logger.debug("Finished sending automatic replies.")
            await asyncio.sleep(30)  # Wait for 4 hours before checking again