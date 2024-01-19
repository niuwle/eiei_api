#app/routers/telegram-webhook.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import add_message
from pydantic import BaseModel, ValidationError
import logging

class TelegramWebhookPayload(BaseModel):
    update_id: int
    message: dict

router = APIRouter()

@router.post("/telegram-webhook/{token}")
async def telegram_webhook(token: str, payload: TelegramWebhookPayload, db: Session = Depends(get_db)):
    try:
        # Security check: verify token
        if token != "Testlocal":  # Replace with your actual secret token
            logging.warning("Invalid token in webhook request")
            raise HTTPException(status_code=403, detail="Invalid token")

        # Validation of payload
        if not payload.message.get('text'):
            logging.warning("No text in the message")
            raise HTTPException(status_code=400, detail="No text found in message")

        # Extract message details
        chat_id = payload.message['chat']['id']
        user_id = payload.message['from']['id']
        message_text = payload.message['text']
        message_id = payload.message['message_id']

        # Convert to your internal message format
        internal_message = TextMessage(
            chat_id=chat_id,
            user_id=user_id,
            bot_id='YOUR_BOT_ID',  # Replace with your bot's ID
            message_text=message_text,
            message_id=message_id,
            channel="TELEGRAM",
            update_id=payload.update_id
        )

        # Process the message
        added_message = add_message(db, internal_message)
        logging.info(f"Message processed successfully: {added_message}")
        return {"status": "Message processed successfully", "details": added_message}
    except ValidationError as ve:
        logging.error(f"Validation error: {ve}")
        raise HTTPException(status_code=422, detail=f"Validation error: {ve}")
    except HTTPException as he:
        logging.error(f"HTTP error: {he.detail}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Don't forget to include this router in your main application
