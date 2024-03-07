# app/utils/process_photo.py
import asyncio
import httpx
import logging
import os
import mimetypes
from app.database_operations import get_bot_config, update_message
from app.config import TELEGRAM_API_URL, HUGGINGFACE_API_TOKEN
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import subprocess
import requests
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from app.controllers.message_processing import process_queue

logger = logging.getLogger(__name__)

async def caption_photo(background_tasks, message_pk: int, ai_placeholder_pk: int, bot_id: int, chat_id: int, user_id: int, file_id: str, db: AsyncSession, user_caption: Optional[str] = None):
    try:
        bot_token = await get_bot_config(db,return_type='token', bot_id=bot_id)
        file_url = f"{TELEGRAM_API_URL}{bot_token}/getFile?file_id={file_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(file_url)
            resp.raise_for_status()
            file_path = resp.json()['result']['file_path']
            photo_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            resp = await client.get(photo_url)
            resp.raise_for_status()
            headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
            caption_resp = await client.post('https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large', content=resp.content, headers=headers)
            caption_resp.raise_for_status()
            caption = caption_resp.json()[0]['generated_text']
            caption_text = f"{caption}. {user_caption}" if user_caption else caption
            logger.info(f"Caption text: {caption_text}")
            await update_message(db, message_pk=message_pk, new_content=caption_text)
            await update_message(db, message_pk=message_pk, new_status="N")
            background_tasks.add_task(process_queue, chat_id=chat_id, bot_id=bot_id, user_id=user_id, message_pk=message_pk, ai_placeholder_pk=ai_placeholder_pk, db=db)
    except Exception as e:
        logger.error(f"Error in caption_photo: {e}")
        await update_message(db, message_pk=message_pk, new_status="E")



