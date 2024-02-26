# In app/database_operations.py
from sqlalchemy.orm import Session
from app.models.message import tbl_msg
from app.models.telegram_config import TelegramConfig
from app.models.awaiting_user_input import tbl_300_awaiting_user_input
from app.models.payments import Payment
from app.models.user_credits import UserCredit
from app.models.user_info import tbl_150_user_info
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import TextMessage
from typing import List, Union
from decimal import Decimal

import logging

logger = logging.getLogger(__name__)

async def get_bot_token(bot_id: int, db: AsyncSession) -> str:
    try:
        query = select(TelegramConfig.bot_token).where(TelegramConfig.pk_bot == bot_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_bot_token: {e}")
        return ''

async def get_bot_id_by_short_name(bot_short_name: str, db: AsyncSession) -> int:
    try:
        query = select(TelegramConfig.pk_bot).where(TelegramConfig.bot_short_name == bot_short_name)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_bot_id_by_short_name: {e}")
        return None


async def add_messages(db: AsyncSession, messages_info: List[dict]) -> List[tbl_msg]:
 
    new_messages = []
    for message_info in messages_info:
        message_data = message_info['message_data']
        role = message_info['role']  # Dynamic role assignment
        type = message_info.get('type', 'TEXT')  # Default type is 'TEXT'
        is_processed = message_info.get('is_processed', 'N')  # Default is_processed status
        
        new_message = tbl_msg(
            chat_id=message_data.chat_id,
            user_id=message_data.user_id,
            bot_id=message_data.bot_id,
            content_text=message_data.message_text,
            message_id=message_data.message_id,
            channel=message_data.channel,
            update_id=message_data.update_id,
            message_date=datetime.now(),
            type=type,
            is_processed=is_processed,
            is_reset='N',
            role=role
        )
        db.add(new_message)
        new_messages.append(new_message)

    await db.commit()
    for new_message in new_messages:
        await db.refresh(new_message)

    logger.debug(f"Messages added: {[message.pk_messages for message in new_messages]}")
    return new_messages

async def update_message_content(db: AsyncSession, message_pk: int, new_content: str):
    try:
        query = select(tbl_msg).where(tbl_msg.pk_messages == message_pk)
        result = await db.execute(query)
        message = result.scalar_one_or_none()
        if message:
            message.content_text = new_content
            await db.commit()
            logger.info(f"Updated content_text for message with pk {message_pk}")
        else:
            logger.warning(f"No message found with pk {message_pk}")
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_message_content: {e}")
        raise

async def mark_message_status(db: AsyncSession, message_pk: int, new_status: str):
    try:
        query = select(tbl_msg).where(tbl_msg.pk_messages == message_pk)
        result = await db.execute(query)
        message = result.scalar_one_or_none()
        if message:
            message.is_processed = new_status
            await db.commit()
            logger.info(f"Message with pk {message_pk} marked as {new_status}")
        else:
            logger.warning(f"No message found with pk {message_pk}")
    except SQLAlchemyError as e:
        logger.error(f"Database error in mark_message_status: {e}")
        raise

async def reset_messages_by_chat_id(db: AsyncSession, chat_id: int) -> None:
    try:
        # Select all messages for the given chat_id
        query = select(tbl_msg).where(tbl_msg.chat_id == chat_id)
        result = await db.execute(query)
        messages = result.scalars().all()

        # Check if there are messages to update
        if messages:
            for message in messages:
                message.is_reset = 'Y' 
            await db.commit()  # Commit changes to the database

            logger.info(f"All messages for chat_id {chat_id} have been marked as reset")
        else:
            logger.warning(f"No messages found for chat_id {chat_id}")

    except SQLAlchemyError as e:
        logger.error(f"Database error in reset_messages_by_chat_id: {e}")
        raise
        
async def mark_chat_as_awaiting(db: AsyncSession, channel: str, chat_id: int, bot_id: int, user_id: int, awaiting_type: str, status: str = "AWAITING"):
    # First, check if a matching record already exists
    existing_query = select(tbl_300_awaiting_user_input).where(
        tbl_300_awaiting_user_input.channel == channel,
        tbl_300_awaiting_user_input.chat_id == chat_id,
        tbl_300_awaiting_user_input.bot_id == bot_id,
        tbl_300_awaiting_user_input.user_id == user_id,
        tbl_300_awaiting_user_input.awaiting_type == awaiting_type,
        tbl_300_awaiting_user_input.status == status
    )
    
    result = await db.execute(existing_query)
    existing_record = result.scalars().first()
    
    # Only proceed to insert if no existing record is found
    if not existing_record:
        new_awaiting_input = tbl_300_awaiting_user_input(
            channel=channel,
            chat_id=chat_id,
            bot_id=bot_id,
            user_id=user_id,
            awaiting_type=awaiting_type,
            status=status
        )
        db.add(new_awaiting_input)
        await db.commit()
        return True  # Return True to indicate a new record was inserted
    else:
        return False  # Return False to indicate no insertion was made

async def check_if_chat_is_awaiting(db: AsyncSession, chat_id: int, awaiting_type: str) -> bool:
    query = select(tbl_300_awaiting_user_input).where(tbl_300_awaiting_user_input.chat_id == chat_id, tbl_300_awaiting_user_input.awaiting_type == awaiting_type, tbl_300_awaiting_user_input.status == "AWAITING")
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def clear_awaiting_status(db: AsyncSession, chat_id: int):
    query = select(tbl_300_awaiting_user_input).where(tbl_300_awaiting_user_input.chat_id == chat_id, tbl_300_awaiting_user_input.status == "AWAITING")
    result = await db.execute(query)
    awaiting_input = result.scalar_one_or_none()
    if awaiting_input:
        awaiting_input.status = "PROCESSED"
        await db.commit()


async def get_bot_assistant_prompt(bot_id: int, db: AsyncSession) -> str:
    try:
        # Select the bot_assistant_prompt column from the tbl_100_telegram_config table where the pk_bot matches the given bot_id
        query = select(TelegramConfig.bot_assistant_prompt).where(TelegramConfig.pk_bot == bot_id)
        result = await db.execute(query)
        # Fetch the first result's scalar value, which should be the bot_assistant_prompt for the given bot_id
        bot_assistant_prompt = result.scalar_one_or_none()
        
        if bot_assistant_prompt:
            logger.info(f"Retrieved bot_assistant_prompt for bot_id {bot_id}")
        else:
            logger.warning(f"No bot_assistant_prompt found for bot_id {bot_id}")
        
        return bot_assistant_prompt
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_bot_assistant_prompt: {e}")
        return ''


async def add_payment_details(db: AsyncSession, payment_info: dict) -> int:
    new_payment = Payment(**payment_info)
    db.add(new_payment)
    await db.commit()
    await db.refresh(new_payment)
    logger.info(f"add_payment_details {new_payment.pk_payment}")
    return new_payment.pk_payment

async def get_latest_total_credits(db: AsyncSession, user_id: int, bot_id: int) -> Decimal:
    try:
        latest_credit = await db.execute(
            select(UserCredit.total_credits)
            .where(UserCredit.user_id == user_id, UserCredit.pk_bot == bot_id)
            .order_by(UserCredit.pk_credit.desc())
            .limit(1)
        )
        latest_credit_value = latest_credit.scalar_one_or_none()
        return Decimal(latest_credit_value) if latest_credit_value is not None else Decimal(0)
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_latest_total_credits: {e}")
        return Decimal(0)

async def update_user_credits(db: AsyncSession, user_credit_info: dict) -> None:
    user_id = user_credit_info['user_id']
    pk_bot = user_credit_info['pk_bot']
    credits_to_add = Decimal(user_credit_info['credits'])

    logger.debug(f"Updating credits for user_id={user_id}, pk_bot={pk_bot}. Adding credits: {credits_to_add}")

    latest_total_credits = await get_latest_total_credits(db, user_id, pk_bot)

    if latest_total_credits is None:
        latest_total_credits = Decimal('0')
        logger.debug(f"No existing credits found for user_id={user_id}. Initializing to 0.")

    updated_total_credits = latest_total_credits + credits_to_add

    logger.debug(f"User_id={user_id} had {latest_total_credits} credits. After adding {credits_to_add}, new total is {updated_total_credits}.")

    user_credit_info['total_credits'] = updated_total_credits

    new_credit = UserCredit(**user_credit_info)
    db.add(new_credit)
    await db.commit()

    logger.info(f"Successfully updated credits for user_id={user_id}. New total credits: {updated_total_credits}. Details: {user_credit_info}")


async def insert_user_if_not_exists(db: AsyncSession, user_data: dict) -> bool:
    # Check if the user already exists
    query = select(tbl_150_user_info).where(
        tbl_150_user_info.id == user_data['id'],
        tbl_150_user_info.pk_bot == user_data['pk_bot'],
        tbl_150_user_info.channel == user_data['channel']
    )
    existing_user = await db.execute(query)
    if existing_user.scalars().first() is not None:
        logger.info("User already exists, skipping insertion.")
        return False  # User already exists

    # Insert the new user
    try:
        new_user = tbl_150_user_info(**user_data)
        db.add(new_user)
        await db.commit()
        logger.info("New user inserted successfully.")

        
        # Adding initial 50 credits gift
        user_credit_info = {
            "channel": "TELEGRAM",  # Or however you determine the channel
            "pk_bot": user_data['pk_bot'],  # Assuming you've retrieved this earlier
            "user_id": user_data['id'],
            "chat_id": user_data['chat_id'],
            "credits": Decimal('50'),  
            "transaction_type": "FIRST_TIME_USER",
            "transaction_date": datetime.utcfromtimestamp(payload_obj.message.date),  # Timestamp of the transaction
            "pk_payment": None
        }
        # Call the function to update user credits
        try:
            await update_user_credits(db, user_credit_info)
        except Exception as e:
            logger.error(f"Failed to update user credits: {e}")
            
        return True
    except IntegrityError as e:
        await db.rollback()
        logger.error(f"Failed to insert new user: {e}")
        return False


async def is_user_banned(db: AsyncSession, id: int, pk_bot: int, channel: str) -> bool:
    query = select(tbl_150_user_info.is_banned).where(
        tbl_150_user_info.id == id,
        tbl_150_user_info.pk_bot == pk_bot,
        tbl_150_user_info.channel == channel
    )
    result = await db.execute(query)
    is_banned = result.scalar_one_or_none()
    if is_banned is None:
        logger.warning("User not found.")
        return False  # Assuming not banned if the user doesn't exist for safety
    return is_banned
