from app.controllers.telegram_integration import (send_credit_purchase_options,
                                                  send_invoice,
                                                  send_telegram_message)
from app.database_operations import mark_chat_as_awaiting


async def handle_callback_query(callback_query, db, bot_short_name, bot_token):
    chat_id = callback_query['message']['chat']['id']
    user_id = callback_query['from']['id']
    data = callback_query['data']

    if data.startswith("buy_"):
        credit_amounts = {
            "buy_100_credits": 500,
            "buy_500_credits": 2000,
            "buy_1000_credits": 3500
        }
        titles = {
            "buy_100_credits": "💎 100 Credits - Unlock More Fun!",
            "buy_500_credits": "🚀 500 Credits - Boost Your Power!",
            "buy_1000_credits": "🌌 1000 Credits - Ultimate Experience!"
        }
        descriptions = {
            "buy_100_credits": "Dive into endless fun with 100 credits.",
            "buy_500_credits": "Amplify the thrill with 500 credits.",
            "buy_1000_credits": "Unlock all features with 1000 credits!"
        }

        amount = credit_amounts.get(data, 0)
        title = titles.get(data, "Credits Pack")
        description = descriptions.get(data, "Get more credits for more interaction.")

        prices = [{"label": "Service Fee", "amount": amount}]
        currency = "USD"
        payload = data

        await send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload,
            currency=currency,
            prices=prices,
            bot_token=bot_token,
            start_parameter="example"
        )

    if data == "generate_photo":
        await mark_chat_as_awaiting(db=db, channel="TELEGRAM", chat_id=chat_id, bot_id=await get_bot_id_by_short_name(bot_short_name, db), user_id=user_id, awaiting_type="PHOTO")
        await send_telegram_message(chat_id=chat_id, text="Please send me the text description for the photo you want to generate", bot_token=bot_token)
    
    if data == "generate_audio":
        await mark_chat_as_awaiting(db=db, channel="TELEGRAM", chat_id=chat_id, bot_id=await get_bot_id_by_short_name(bot_short_name, db), user_id=user_id, awaiting_type="AUDIO")
        await send_telegram_message(chat_id=chat_id, text="Please tell me what you want to hear", bot_token=bot_token)
   
    if data == "ask_credit":
        await send_credit_purchase_options(chat_id, bot_token)

    return {"status": "Callback query processed successfully"}
