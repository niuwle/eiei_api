# app/utils/generate_photo.py
import httpx
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

# Set up logging
logger = logging.getLogger(__name__)


async def generate_photo_from_text(text: str, db: AsyncSession) -> Optional[str]:
    """
    For testing purposes, this function now skips actual photo generation
    and returns a static URL to a specific jpg file.

    Parameters:
    - text (str): The text description (unused in this mock implementation).
    - db (AsyncSession): The database session (unused in this mock implementation).

    Returns:
    - Optional[str]: The URL of the specific jpg file for testing purposes.
    """
    # Mock URL to the jpg file - replace with the actual URL where the jpg file is accessible
    photo_url = "https://eiei-api.onrender.com/static/cats.jpg"

    return photo_url

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
