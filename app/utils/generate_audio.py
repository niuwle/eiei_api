# app/routers/generate_audio.py
import requests
import httpx
import uuid
import logging
import aiofiles 
import asyncio
import os
logger = logging.getLogger(__name__)
from app.config import ELEVENLABS_KEY, MONSTER_API_TOKEN
from typing import Optional


TEMP_DIR = "./temp_audio_files"  # Temporary storage directory 

async def generate_audio_with_monsterapi(text: str) -> Optional[str]:
    API_Key = MONSTER_API_TOKEN  # Your MonsterAPI API key
    url = "https://api.monsterapi.ai/v1/generate/sunoai-bark"

    payload = {
        "prompt": text
    }

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {API_Key}"
    }

    try:
        async with httpx.AsyncClient() as client:
            # Make the asynchronous POST request for audio generation
            gen_response = await client.post(url, json=payload, headers=headers)
            gen_response.raise_for_status()
            gen_response_json = gen_response.json()
            logger.info(f"Audio generation initiated: {gen_response_json}")

            process_id = gen_response_json.get('process_id', '')
            status_url = gen_response_json.get('status_url', '')  # Use the provided status URL

            # Initialize variables for status check loop
            max_attempts = 5
            attempt_count = 0
            status = ''

            # Continuously check for the result
            while attempt_count < max_attempts and status != 'COMPLETED':
                await asyncio.sleep(5)  # Wait before checking the status
                status_response = await client.get(status_url, headers=headers)
                status_response.raise_for_status()
                status_json = status_response.json()
                status = status_json.get('status', '')
                attempt_count += 1

                if status == 'COMPLETED':
                    logger.info(f"Audio generation completed: {status_json}")
                    # Download the audio file and save it locally
                    audio_url = status_json.get('result', {}).get('output', [])[0]
                    if audio_url:
                        audio_filename = f"monsterapi_audio_{uuid.uuid4()}.mp3"
                        audio_response = await client.get(audio_url)
                        async with aiofiles.open(audio_filename, 'wb') as audio_file:
                            await audio_file.write(audio_response.content)
                        logger.info(f"Audio file saved: {audio_filename}")
                        return audio_filename  # Return the local path of the downloaded audio file
                    break
                elif status == 'FAILED':
                    logger.error(f"Audio generation failed {status_json}")
                    return None

            if status != 'COMPLETED':
                logger.error("Audio generation did not complete in time")
                return None

    except Exception as e:
        logger.error(f"Error in generate_audio_with_monsterapi: {e}")
        return None

        
async def generate_audio_from_text(text: str, voice_id: str) -> str:
    
    logger.debug(f"Generation audio") # Debug statement
    """
    Generates an audio file from the provided text using the ElevenLabs API.

    Parameters:
    - text (str): The text to convert to speech.

    Returns:
    - str: The file path to the generated audio file.
    """

    XI_API_KEY = ELEVENLABS_KEY  # Replace with your ElevenLabs API key
    #voice_id = "TFx9mJ79I0uOwtOH3LV9"  # Hardcoded voice ID
    voice_id = voice_id  # Hardcoded voice ID Para obtener buscar aca https://api.elevenlabs.io/v1/text-to-speech/UVxc67Ct0LcVox2mvQA1/stream?
    tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    logger.debug(f"tts_url: {tts_url}")
    headers = {
        "Content-Type": "application/json",
        "xi-api-key": XI_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.05,
            "similarity_boost": 1,
            "style": 0.85
        }
    }

    # Ensure the temporary directory exists
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    response = requests.post(tts_url, json=data, headers=headers, stream=True)
    if response.status_code == 200:
        # Save the file in the TEMP_DIR directory
        filename = f"{TEMP_DIR}/elevenlabs_{uuid.uuid4()}.mp3"
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        logger.debug(f"Audio file saved to {filename}")
        return filename
    else:
        error_message = f"Error from ElevenLabs API: Status Code {response.status_code}, Response: {response.text}"
        logger.error(error_message)
        raise Exception(error_message)