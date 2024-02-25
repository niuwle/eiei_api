from datetime import datetime

from app.controllers.telegram_integration import (answer_pre_checkout_query,
                                                  get_latest_total_credits,
                                                  send_credit_count,
                                                  send_telegram_message)
from app.database_operations import add_payment_details, update_user_credits


async def handle_pre_checkout_query(pre_checkout_query, bot_token):
    pre_checkout_query_id = pre_checkout_query.id
    try:
        await answer_pre_checkout_query(pre_checkout_query_id, ok=True, bot_token=bot_token)
    except Exception as e:
        raise e

async def handle_successful_payment(message, db, bot_token):
    successful_payment = message.successful_payment
    payment_info = {
        "update_id": message.update_id,
        "message_id": message.message_id,
        "user_id": message.from_.get('id'),
        "user_is_bot": message.from_.get('is_bot', False),
        "user_first_name": message.from_.get('first_name', ''),
        "user_language_code": message.from_.get('language_code', ''),
        "chat_id": message.chat.get('id'),
        "chat_first_name": message.chat.get('first_name', ''),
        "chat_type": message.chat.get('type', ''),
        "payment_date": datetime.utcfromtimestamp(message.date),
        "currency": successful_payment.currency,
        "total_amount": successful_payment.total_amount / 100.0,
        "invoice_payload": successful_payment.invoice_payload,
        "telegram_payment_charge_id": successful_payment.telegram_payment_charge_id,
        "provider_payment_charge_id": successful_payment.provider_payment_charge_id
    }
    pk_payment = await add_payment_details(db, payment_info)
    user_credit_info = {
        "channel": "TELEGRAM",
        "pk_bot": message.bot_id,
        "user_id": message.from_.get('id'),
        "chat_id": message.chat.get('id'),
        "credits": 10,
        "transaction_type": "PAYMENT",
        "transaction_date": datetime.utcfromtimestamp(message.date),
        "pk_payment": pk_payment
    }
    await update_user_credits(db, user_credit_info)
    confirmation_text = "Thank you for your payment! 💋💋💋"
    await send_telegram_message(message.chat['id'], confirmation_text, bot_token)
    total_credits = await get_latest_total_credits(db=db, user_id=message.from_.get('id'), bot_id=message.bot_id)
    await send_credit_count(message.chat['id'], bot_token=bot_token, total_credits=total_credits)
