# app/routers/error_handler.py
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

def handle_exception(e, status_code=500, detail=""):
    logger.error(f"Unexpected error: {str(e)}")
    raise HTTPException(status_code=status_code, detail=detail)
