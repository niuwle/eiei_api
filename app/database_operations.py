# app/database_operations.py
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from datetime import datetime
from decimal import Decimal
from typing import List, Union, Type



from app.models import (
    tbl_msg, TelegramConfig, tbl_300_awaiting_user_input,
    Payment, UserCredit, tbl_150_user_info
)
from app.schemas import TextMessage

import logging

logger = logging.getLogger(__name__)

async def get_bot_config(db: AsyncSession, return_type: str = None, bot_id: int = None, bot_short_name: str = None) -> Union[str, int, tuple, None]:
    try:
        async with db as session:
            
            if bot_id is not None:
                logger.debug(f"Fetching bot config for bot_id: {bot_id}")
                query = select(TelegramConfig.bot_token, TelegramConfig.bot_short_name).where(TelegramConfig.pk_bot == bot_id)
                result = await session.execute(query)
                bot_config = result.one_or_none()
                logger.debug(f"Bot config fetched for bot_id {bot_id}: {bot_config}")
                if bot_config:
                    bot_token, bot_short_name = bot_config
                    logger.debug(f"Extracted bot_token: {bot_token}, bot_short_name: {bot_short_name}")
                    if return_type == 'token':
                        logger.debug(f"Returning bot_token: {bot_token}")
                        return bot_token
                    elif return_type == 'short_name':
                        logger.debug(f"Returning bot_short_name: {bot_short_name}")
                        return bot_short_name
                    else:
                        logger.debug(f"Returning both bot_token and bot_short_name")
                        return bot_token, bot_short_name
            elif bot_short_name is not None:
                logger.debug(f"Fetching bot_id for bot_short_name: {bot_short_name}")
                query = select(TelegramConfig.pk_bot).where(TelegramConfig.bot_short_name == bot_short_name)
                result = await session.execute(query)
                bot_id = result.scalar_one_or_none()
                logger.debug(f"Fetched bot_id {bot_id} for bot_short_name: {bot_short_name}")
                return bot_id
            else:
                logger.debug("No bot_id or bot_short_name provided")
                return None
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_bot_config: {e}")
        return None

async def add_messages(db: AsyncSession, messages_info: List[dict]) -> List[Type[tbl_msg]]:
    new_messages = []
    for message_info in messages_info:
        message_data = message_info['message_data']
        role = message_info['role']
        message_type = message_info.get('type', 'TEXT')
        is_processed = message_info.get('is_processed', 'N')

        new_message = tbl_msg(
            chat_id=message_data.chat_id,
            user_id=message_data.user_id,
            bot_id=message_data.bot_id,
            content_text=message_data.message_text,
            message_id=message_data.message_id,
            channel=message_data.channel,
            update_id=message_data.update_id,
            message_date=datetime.now(),
            type=message_type,
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



async def update_message(db: AsyncSession, message_pk: int, new_content: str = None, new_status: str = None):
    try:
        query = select(tbl_msg).where(tbl_msg.pk_messages == message_pk)
        result = await db.execute(query)
        message = result.scalar_one_or_none()
        if message:
            if new_content:
                message.content_text = new_content
                logger.info(f"Updated content_text for message with pk {message_pk}")
            if new_status:
                message.is_processed = new_status
                logger.info(f"Message with pk {message_pk} marked as {new_status}")
            await db.commit()
        else:
            logger.warning(f"No message found with pk {message_pk}")
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_message: {e}")
        raise


async def reset_messages_by_chat_id(db: AsyncSession, chat_id: int) -> None:
    try:
        query = select(tbl_msg).where(tbl_msg.chat_id == chat_id)
        result = await db.execute(query)
        messages = result.scalars().all()

        if messages:
            for message in messages:
                message.is_reset = 'Y'
            await db.commit()
            logger.info(f"All messages for chat_id {chat_id} have been marked as reset")
        else:
            logger.warning(f"No messages found for chat_id {chat_id}")

    except SQLAlchemyError as e:
        logger.error(f"Database error in reset_messages_by_chat_id: {e}")
        raise

async def manage_awaiting_status(db: AsyncSession, channel: str, chat_id: int, bot_id: int = None, user_id: int = None,
                                 awaiting_type: str = None, status: str = "AWAITING", action: str = "INSERT"):
    try:
        if action == "REMOVE":
            # Update all records with the given chat_id to "PROCESSED" status
            update_stmt = (
                update(tbl_300_awaiting_user_input)
                .where(tbl_300_awaiting_user_input.chat_id == chat_id)
                .values(status="PROCESSED")
            )
            await db.execute(update_stmt)
            await db.commit()
            return True

        existing_query = select(tbl_300_awaiting_user_input).where(
            tbl_300_awaiting_user_input.channel == channel,
            tbl_300_awaiting_user_input.chat_id == chat_id,
            tbl_300_awaiting_user_input.bot_id == bot_id,
            tbl_300_awaiting_user_input.user_id == user_id,
            tbl_300_awaiting_user_input.awaiting_type == awaiting_type,
            tbl_300_awaiting_user_input.status == status
        )
        existing_record = await db.execute(existing_query)
        existing_record = existing_record.scalar_one_or_none()

        if action == "INSERT" and not existing_record:
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
            return True
        elif action == "UPDATE" and existing_record:
            existing_record.status = "PROCESSED"
            await db.commit()
            return True
        else:
            return False
    except SQLAlchemyError as e:
        logger.error(f"Database error in manage_awaiting_status: {e}")
        return False


async def check_if_chat_is_awaiting(db: AsyncSession, chat_id: int, awaiting_type: str) -> bool:
    query = select(tbl_300_awaiting_user_input).where(
        tbl_300_awaiting_user_input.chat_id == chat_id,
        tbl_300_awaiting_user_input.awaiting_type == awaiting_type,
        tbl_300_awaiting_user_input.status == "AWAITING"
    )
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def get_bot_assistant_prompt(bot_id: int, db: AsyncSession) -> str:
    try:
        query = select(TelegramConfig.bot_assistant_prompt).where(TelegramConfig.pk_bot == bot_id)
        result = await db.execute(query)
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
    query = select(tbl_150_user_info).where(
        tbl_150_user_info.id == user_data['id'],
        tbl_150_user_info.pk_bot == user_data['pk_bot'],
        tbl_150_user_info.channel == user_data['channel']
    )
    existing_user = await db.execute(query)
    if existing_user.scalars().first() is not None:
        logger.info("User already exists, skipping insertion.")
        return False

    try:
        new_user = tbl_150_user_info(**user_data)
        db.add(new_user)
        await db.commit()
        logger.info("New user inserted successfully.")

        # Adding initial 50 credits gift
        user_credit_info = {
            "channel": "TELEGRAM",
            "pk_bot": user_data['pk_bot'],
            "user_id": user_data['id'],
            "chat_id": user_data['chat_id'],
            "credits": Decimal('50'),
            "transaction_type": "FIRST_TIME_USER",
            "transaction_date": datetime.utcnow(),
            "pk_payment": None
        }
        await update_user_credits(db, user_credit_info)
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