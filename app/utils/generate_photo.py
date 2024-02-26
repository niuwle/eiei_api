# app/utils/generate_photo.py
import httpx
import logging
from sqlalchemy.ext.asyncio import AsyncSession
import random
import asyncio
from typing import Optional
from b2sdk.v1 import InMemoryAccountInfo, B2Api
from app.config import B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME
from .file_list_cache import get_cached_file_list
# Set up logging
logger = logging.getLogger(__name__)


# Function to generate a signed URL
async def generate_signed_url(file_id: str) -> Optional[str]:
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    valid_duration_in_seconds = 3600  # or any duration you prefer
    b2_authorization_token = bucket.get_download_authorization(file_id, valid_duration_in_seconds)
    signed_url = f"https://f005.backblazeb2.com/file/{B2_BUCKET_NAME}/{file_id}?Authorization={b2_authorization_token}"
    logger.info(f"signed_url URL: {signed_url}")
    return signed_url

# Function to get a random photo URL from the cached list
async def get_random_photo_url() -> Optional[str]:
    file_info = await get_cached_file_list()
    if not file_info:
        logger.error("No file info available in cache.")
        return None
    
    # Select a random file
    file_id = random.choice(list(file_info.keys()))
    logger.info(f"Selected file ID for generating signed URL: {file_id}")
    
    # Generate and return the signed URL
    return await generate_signed_url(file_id)

# Example function that uses the get_random_photo_url
async def generate_photo_from_text(text: str) -> Optional[str]:
    """
    Generates a signed URL for a random photo from the B2 bucket based on cached file list.
    """
    try:
        photo_url = await get_random_photo_url()
        return photo_url
    except Exception as e:
        logger.error(f"Failed to generate photo from text: {str(e)}")
        return None


async def generate_photo_from_textFUTURE(text: str, db: AsyncSession) -> Optional[str]:
    """
    Generates a photo based on the given text description.

    Parameters:
    - text (str): The text description to generate the photo from.
    - db (AsyncSession): The database session for any needed database operations.

    Returns:
    - Optional[str]: The URL of the generated photo, or None if the generation failed.
    """
    # Define the API URL and your API key
    api_url = "https://api.example.com/generate-photo"
    api_key = YOUR_API_KEY_HERE  # Replace with your actual API key

    # Set up the headers and payload for the API request
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
    }

    # Try to make the request to the API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload, headers=headers)
        response.raise_for_status()

        # If the request was successful, parse the response
        data = response.json()
        photo_url = data.get("photo_url")  # Adjust this based on the actual API response structure

        return photo_url
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred while generating photo: {e}")
    except Exception as e:
        logger.error(f"Unexpected error occurred while generating photo: {str(e)}")

    # Return None if there was an error
    return None
