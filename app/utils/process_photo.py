# app/routers/process_photo.py
import asyncio
import httpx
import logging
import os
import mimetypes
from app.database_operations import get_bot_token, mark_message_status, update_message_content
from app.config import TELEGRAM_API_URL, HUGGINGFACE_API_TOKEN
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import subprocess
import requests
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from app.controllers.message_processing import process_queue

logger = logging.getLogger(__name__)

async def caption_photo(background_tasks: BackgroundTasks, message_pk: int, ai_placeholder_rec: int,  bot_id: int, chat_id: int, file_id: str, db: AsyncSession) -> Optional[str]:
    try:
        bot_token = await get_bot_token(bot_id=bot_id, db=db)
        file_url = f"{TELEGRAM_API_URL}{bot_token}/getFile?file_id={file_id}"

        async with httpx.AsyncClient() as client:
            file_response = await client.get(file_url)
            file_response.raise_for_status()

            file_path = file_response.json().get("result", {}).get("file_path", "")
            full_file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

            # Download the photo file
            photo_response = await client.get(full_file_url)
            photo_response.raise_for_status()

            # Set up the headers and send the request to Hugging Face API
            headers = {
                "Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"
            }

            # Send the binary data of the photo directly in the request body
            caption_response = await client.post(
                'https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large',
                content=photo_response.content,
                headers=headers
            )

            caption_response.raise_for_status()
            caption_json = caption_response.json()
            caption_text = caption_json[0].get('generated_text', '[Photo]: Captioning failed or incomplete')

            # Handle the response
            logger.info(f"Caption text: {caption_text}")
            await update_message_content(db, message_pk, caption_text)
            await mark_message_status(db, message_pk, 'N')
            background_tasks.add_task(process_queue, chat_id, ai_placeholder_rec.pk_messages, db)

    except Exception as e:
        logger.error(f"Error in process_photo: {e}")
        await mark_message_status(db, message_pk, 'E')
        return None

