# app/controllers/ai_communication.py
import requests
import logging
from sqlalchemy.orm import Session
from app.models.message import tbl_msg
from typing import Optional
from app.config import OPENROUTER_TOKEN, OPENROUTER_MODEL, OPENROUTER_URL, ASSISTANT_PROMPT

def get_chat_completion(chat_id: int, bot_id: int, db: Session) -> Optional[str]:
    try:
        logging.info(f"Getting chat completion for chat_id: {chat_id} and bot_id: {bot_id}")
        messages = db.query(tbl_msg).filter(tbl_msg.chat_id == chat_id, tbl_msg.bot_id == bot_id).order_by(tbl_msg.message_date).all()

        payload = {"model": OPENROUTER_MODEL, "max_tokens": 4024, "messages": [{"role": "system", "content": ASSISTANT_PROMPT}]}
        for message in messages:
            payload["messages"].append({"role": message.role.lower(), "content": message.content_text})

        logging.debug("Payload for AI service: %s", payload)

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENROUTER_TOKEN}"}
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers)
        response_data = response.json()

        logging.info("Received response from AI service.")
        logging.debug("JSON from OpenROUTER: %s", response_data)
        return response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

    except Exception as e:
        logging.error(f"Error in get_chat_completion: {str(e)}")
        return None
