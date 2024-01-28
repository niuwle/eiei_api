import asyncio
import httpx
import logging
import os
import mimetypes
from app.database_operations import get_bot_token, mark_message_status, update_message_content
from app.config import TELEGRAM_API_URL, MONSTER_API_TOKEN
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import subprocess
import requests
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from app.controllers.message_processing import process_queue

logger = logging.getLogger(__name__)
async def transcribe_audio(background_tasks: BackgroundTasks,  message_pk: int, bot_id: int, chat_id: int, file_id: str, db: AsyncSession) -> Optional[str]:
    try:
        bot_token = await get_bot_token(bot_id=bot_id, db=db)
        file_url = f"{TELEGRAM_API_URL}{bot_token}/getFile?file_id={file_id}"

        async with httpx.AsyncClient() as client:
            # Get the file from Telegram
            file_response = await client.get(file_url)
            file_response.raise_for_status()

            file_path = file_response.json().get("result", {}).get("file_path", "")
            full_file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

            logger.info(f"full_file_url {full_file_url}")

            # Convert audio file format
            converted_file_path = await convert_audio(full_file_url)

            # Prepare the file for upload
            file_name = os.path.basename(converted_file_path)
            files = {
                "file": (file_name, open(converted_file_path, "rb"), mimetypes.guess_type(converted_file_path)[0])
            }
            payload = {
                "diarize": "true",
                "language": "en"
            }
            headers = {
                "accept": "application/json",
                "authorization": f"Bearer {MONSTER_API_TOKEN}"
            }

            # Send the transcription request with the file
            transcription_response = await client.post(
                'https://api.monsterapi.ai/v1/generate/whisper',
                data=payload,
                files=files,
                headers=headers
            )
            logger.info(f"Monster transcription_response {transcription_response}")

            transcription_response.raise_for_status()
            transcribed_text = transcription_response.json().get('text', '')

            logger.info(f"transcribed_text {transcribed_text}")

        # Check if transcribed text is empty
        if not transcribed_text:
            error_message = "Transcription failed or returned empty result."
            logger.error(error_message)

            # Update the database with an error message
            await update_message_content(db, message_pk, error_message)

        else:
            logger.info(f"transcribed_text {transcribed_text}")

            # Update the database with the transcription result
            await update_message_content(db, message_pk, transcribed_text)

        # Mark the message status as 'N' for start processing
        await mark_message_status(db, message_pk, 'N')
        # Clean up the temporary file
        os.remove(converted_file_path)

        # Continue with processing
        background_tasks.add_task(process_queue, chat_id, db)

    except Exception as e:
        logger.error(f"Error in transcribe_audio: {e}")
        await mark_message_status(db, message_pk, 'E')  # Update your function signature if needed
        return None


async def convert_audio(file_url: str) -> str:
    try:
        response = requests.get(file_url)
        if response.status_code != 200:
            logger.error('Failed to download the file')
            return ''

        with NamedTemporaryFile(suffix='.oga', delete=True) as input_file:  # Changed to delete=True for cleanup
            input_file.write(response.content)
            input_file.flush()  # Ensure all data is written

            # Convert .oga to .ogg
            output_filename = input_file.name + '.ogg'
            subprocess.run(['ffmpeg', '-i', input_file.name, output_filename], check=True)

            return output_filename

    except subprocess.CalledProcessError as e:
        logger.error(f'Failed to convert the file: {e}')
    except Exception as e:
        logger.error(f'An error occurred during audio conversion: {e}')

    return ''
