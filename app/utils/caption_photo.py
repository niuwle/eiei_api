# app/utils/caption_photo.py
import aiofiles
import asyncio
import httpx
import logging
from app.config import HUGGINGFACE_API_TOKEN

logger = logging.getLogger(__name__)

async def get_caption_for_local_photo(photo_file_path: str) -> str:
    logger.debug(f"Doing caption of {photo_file_path}")
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
    services = [
        'https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large',
        'https://api-inference.huggingface.co/models/nlpconnect/vit-gpt2-image-captioning'
    ]
    caption = None

    async with httpx.AsyncClient() as client:
        async with aiofiles.open(photo_file_path, "rb") as file:
            photo_content = await file.read()
            for attempt in range(5):
                for service in services:
                    try:
                        caption_resp = await client.post(service, content=photo_content, headers=headers)
                        caption_resp.raise_for_status()
                        caption = caption_resp.json()[0]['generated_text']
                        if caption:
                            logger.debug(f"Caption generated {caption}")
                            return caption
                    except Exception as e:
                        logger.error(f"Service {service} failed with error: {e}")
                        await asyncio.sleep(5)  # Wait for 5 seconds before retrying
    if not caption:
        raise Exception("Caption service unavailable after 5 attempts.")
