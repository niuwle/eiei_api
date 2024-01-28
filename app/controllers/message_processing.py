# ./app/controllers/message_processing.py
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.database_operations import get_bot_token, add_message, mark_message_status
from app.controllers.ai_communication import get_chat_completion
from app.controllers.telegram_integration import send_telegram_message
from app.models.message import tbl_msg
from app.models import message  # Ensure this is imported
from sqlalchemy.future import select
from app.schemas import TextMessage
import asyncio
import re

logger = logging.getLogger(__name__)

async def process_queue(chat_id: int, db: AsyncSession):
    try:
        timestamp = datetime.now()
        await asyncio.sleep(3)
        logger.info(f"Processing queue for chat_id {chat_id} as of {timestamp}")

        stmt = select(tbl_msg).where(tbl_msg.chat_id == chat_id, tbl_msg.is_processed == 'N').order_by(tbl_msg.message_date.desc())
        async with db:
            result = await db.execute(stmt)
            unprocessed_messages = result.scalars().all()

        logger.info(f"Unprocessed messages: {unprocessed_messages}") 

        logger.debug(f"Unprocessed messages: {unprocessed_messages}") # Debug statement

        if unprocessed_messages:
            logger.info(f"Comparing message_date {unprocessed_messages[0].message_date} and timestamp {timestamp}")

            if unprocessed_messages[0].message_date <= timestamp:
                await process_message(unprocessed_messages, db, chat_id)
            else:
                # Skip processing as a new message arrived during the wait
                logger.info(f"Skipping processing: New message for chat_id {chat_id} arrived during wait.")
            
            
    except Exception as e:
        logger.error(f'Error processing queue: {e}')
        await db.rollback()
    finally:
        await db.close()


async def process_message(messages, db, chat_id):
    logger.debug(f"Messages to process: {messages}") # Debug statement

    # Mark all messages as processed once
    for message in messages:
        await mark_message_status(db, message.pk_messages, 'P')

    # Get chat completion only once
    try:
        response_text = await asyncio.wait_for(get_chat_completion(chat_id, messages[0].bot_id, db), timeout=10)
    except asyncio.TimeoutError:
        logger.error(f"get_chat_completion timed out for chat_id {chat_id}")
        response_text = None
        
    logger.debug(f"Chat completion response: {response_text}") # Debug statement

    if response_text:
        # Apply humanization to the response text
        humanized_response = humanize_response(response_text)
        bot_token = await get_bot_token(messages[0].bot_id, db)

        # Loop through each sentence and send it as a separate message
        for sentence in humanized_response.split('\n'):
            if sentence.strip():  # Ensure the sentence is not just whitespace
                await send_telegram_message(chat_id, sentence, bot_token)
        
        # Construct the message data for the response message
        response_message_data = TextMessage(
            chat_id=chat_id,
            user_id=0, # Assuming the bot is sending the message, user_id might be set to 0 or the bot's user ID
            bot_id=messages[0].bot_id,
            message_text=response_text,
            message_id=0, # If you have a way to generate or track message IDs for outgoing messages, use it here
            channel=messages[0].channel,
            update_id=0 # Set to 0 or an appropriate value if you're tracking update IDs
        )

        # Use the updated add_message function to save the response
        await add_message(db, response_message_data, type='TEXT', is_processed='Y', role='ASSISTANT')

    # Mark all messages as processed again
    for message in messages:
        await mark_message_status(db, message.pk_messages, 'Y')

    # Log the count of records processed
    logger.info(f"{len(messages)} messages processed for chat_id {chat_id}")


def humanize_response(text: str) -> str:
    # Using regular expression to split the text into sentences at '.', '?', and '!'
    # Lookahead assertion is used to keep the punctuation marks
    sentences = re.split(r'(?<=[.?!])\s+', text)

    # Removing initial Spanish question marks (¿), exclamation marks (¡) and processing each sentence
    formatted_sentences = []
    for s in sentences:
        if s:
            s = s.lstrip('¿¡')  # Remove leading special characters
            s = re.sub(r'(\d+\.)', r'\n\1', s)  # Add newline before numbers followed by a period
            s = re.sub(r'(?<=[^\d\n])([A-Z][^.!?]*[.!?])', r'\n\1', s)  # Add newline before certain sentences
            formatted_sentences.append(s)

    # Joining the formatted sentences with a new line to simulate separate message sending
    humanized_text = '\n'.join(formatted_sentences).strip()

    return humanized_text
