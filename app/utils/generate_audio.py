# app/routers/generate_audio.py
import requests
import httpx
import uuid
import logging
import aiofiles 
logger = logging.getLogger(__name__)
from app.config import ELEVENLABS_KEY

async def generate_audio_from_text(text: str) -> str:
    XI_API_KEY = ELEVENLABS_KEY  # Your ElevenLabs API key
    voice_id = "UVxc67Ct0LcVox2mvQA1"  # The voice ID for the text-to-speech conversion
    tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",  # Specify the response content type you're expecting
        "xi-api-key": XI_API_KEY
    }

    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",  # Use the model ID from the documentation
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
            # Include any other settings as per your requirement
        }
    }


    # Make the asynchronous POST request
    async with httpx.AsyncClient() as client:
        response = await client.post(tts_url, json=data, headers=headers)

    if response.status_code ==  200:
        filename = f"elevenlabs_output_{uuid.uuid4()}.mp3"
        async with aiofiles.open(filename, 'wb') as f:
            async for chunk in response.aiter_bytes():
                await f.write(chunk)
        return filename
    else:
        error_message = f"Error from ElevenLabs API: Status Code {response.status_code}, Response: {response.text}"
        logger.error(error_message)
        raise Exception(error_message)

        
def generate_audio_from_text2(text: str) -> str:
    
    logger.debug(f"Generation audio") # Debug statement
    """
    Generates an audio file from the provided text using the ElevenLabs API.

    Parameters:
    - text (str): The text to convert to speech.

    Returns:
    - str: The file path to the generated audio file.
    """
    XI_API_KEY = "2545f09564eb96f3a0019c14f9a11bee"  # Replace with your ElevenLabs API key
    #voice_id = "TFx9mJ79I0uOwtOH3LV9"  # Hardcoded voice ID
    voice_id = "UVxc67Ct0LcVox2mvQA1"  # Hardcoded voice ID Para obtener buscar aca https://api.elevenlabs.io/v1/text-to-speech/UVxc67Ct0LcVox2mvQA1/stream?
    tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
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
            "style": 0
        }
    }

    response = requests.post(tts_url, json=data, headers=headers, stream=True)
    if response.status_code == 200:
        filename = f"elevenlabs_{uuid.uuid4()}.mp3"
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        return filename
    else:
        error_message = f"Error from ElevenLabs API: Status Code {response.status_code}, Response: {response.text}"
        raise Exception(error_message)