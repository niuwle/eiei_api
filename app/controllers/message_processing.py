# app/controllers/message_processing.py
import logging
from datetime import datetime, timedelta
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.database_operations import get_bot_token, insert_response_message, mark_messages_processed
from app.controllers.ai_communication import get_chat_completion
from app.controllers.telegram_integration import send_telegram_message
from app.models.message import tbl_msg

def process_queue():
    db = next(get_db())
    try:
        current_time = datetime.now()
        logging.info("Processing queue at: %s", current_time)
        
        messages = db.query(tbl_msg).filter(
            tbl_msg.is_processed == 'N', 
            tbl_msg.message_date < current_time - timedelta(seconds=3)
        ).all()

        if not messages:
            logging.info("No new messages to process.")

        for message in messages:
            logging.info(f"Processing message: {message.message_id}")
            chat_id = message.chat_id
            bot_id = message.bot_id
            bot_token = get_bot_token(bot_id, db)

            response_text = get_chat_completion(chat_id, bot_id, db)
            if response_text:
                telegram_response = send_telegram_message(chat_id, response_text, bot_token)
                logging.info(f'Response from Telegram: {telegram_response}')
                insert_response_message(db, 'TELEGRAM', bot_id, chat_id, response_text,'TEXT','ASSISTANT','Y')

        # After processing all messages and sending responses, mark all messages as processed
        if messages:
            mark_messages_processed(db, chat_id, bot_id)

    except Exception as e:
        logging.error(f'Error in process_queue: {str(e)}')
        db.rollback()
        raise
    finally:
        db.close()
        logging.info("Queue processing completed.")

def check_new_messages():
    logging.info("Checking for new messages.")
    process_queue()
