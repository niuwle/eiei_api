# app/routers/message_controller.py
from fastapi import APIRouter, HTTPException
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import add_message
from app.controllers.message_processing import process_queue
import asyncio

router = APIRouter()

@router.post("/receive-message")
async def receive_message(message: TextMessage):
    async with get_db() as db:
        try:
            added_message = await add_message(db, message)
            await process_queue(added_message.chat_id, db)
            return {"pk_messages": added_message.pk_messages, "status": "Message saved successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
