# app/utils/process_photo.py
import asyncio
import httpx
import logging
import os
import mimetypes
from app.database_operations import update_message
from app.config import TELEGRAM_API_URL, HUGGINGFACE_API_TOKEN
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.database import get_db
import subprocess
import requests
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from app.controllers.message_processing import process_queue
from app.config import bot_config

logger = logging.getLogger(__name__)

async def caption_photo(background_tasks, message_pk: int, ai_placeholder_pk: int, bot_id: int, chat_id: int, user_id: int, file_id: str, request: Request,db: AsyncSession = Depends(get_db), user_caption: Optional[str] = None):

    try:
        bot_token = bot_config["bot_token"]
        file_url = f"{TELEGRAM_API_URL}{bot_token}/getFile?file_id={file_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(file_url)
            resp.raise_for_status()
            file_path = resp.json()['result']['file_path']
            photo_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            resp = await client.get(photo_url)
            resp.raise_for_status()

            headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
            services = [
                'https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large',
                'https://api-inference.huggingface.co/models/nlpconnect/vit-gpt2-image-captioning'
            ]
            caption = None
            for attempt in range(5):
                for service in services:
                    try:
                        caption_resp = await client.post(service, content=resp.content, headers=headers)
                        caption_resp.raise_for_status()
                        caption = caption_resp.json()[0]['generated_text']
                        if caption:
                            break
                    except Exception as e:
                        logger.error(f"Service {service} failed with error: {e}")
                        await asyncio.sleep(5)  # Wait for 5 seconds before retrying
                if caption:
                    break
            
            if not caption:
                raise Exception("Caption service unavailable after 5 attempts.")

            caption_text = f"{caption}. {user_caption}" if user_caption else caption
            logger.info(f"Caption text: {caption_text}")
            await update_message(db, message_pk=message_pk, new_content=caption_text)
            await update_message(db, message_pk=message_pk, new_status="N")
            background_tasks.add_task(process_queue, chat_id=chat_id, bot_id=bot_id, user_id=user_id, message_pk=message_pk, ai_placeholder_pk=ai_placeholder_pk, request=request, db=db)
    except Exception as e:
        logger.error(f"Error in caption_photo: {e}")
        await update_message(db, message_pk=message_pk, new_status="E")


