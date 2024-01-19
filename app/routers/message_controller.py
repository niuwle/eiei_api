#app/routers/message_controller.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.message import tbl_msg
from app.schemas import TextMessage
from app.database import get_db
from app.database_operations import add_message

router = APIRouter()

@router.post("/receive-message", status_code=status.HTTP_200_OK)
def receive_message(message: TextMessage, db: Session = Depends(get_db)):
    try:
        added_message = add_message(db, message)
        return {"pk_messages": added_message.pk_messages, "status": "Message saved successfully"}
    except Exception as e:
        # Return the error code along with the message
        raise HTTPException(status_code=400, detail=f"An error occurred while saving the message. Error: {str(e)}")
