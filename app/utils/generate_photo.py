# app/utils/generate_photo.py
import httpx
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
import random
import asyncio
from typing import Optional
from b2sdk.v1 import InMemoryAccountInfo, B2Api
from app.config import B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME, HOST_URL
from .file_list_cache import get_cached_file_list
from app.controllers.ai_communication import get_photo_filename
from datetime import datetime, timedelta
import os
import shutil
from fastapi import APIRouter, HTTPException, BackgroundTasks

TEMP_DIR = "./temp_files"  # Temporary storage directory

# Set up logging
logger = logging.getLogger(__name__)


# Function to generate a signed URL
async def generate_signed_url(filename: str) -> Optional[str]:
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    valid_duration_in_seconds = 3600  # or any duration you prefer
    b2_authorization_token = bucket.get_download_authorization(filename, valid_duration_in_seconds)
    signed_url = f"https://f005.backblazeb2.com/file/{B2_BUCKET_NAME}/{file_id}?Authorization={b2_authorization_token}"
    logger.info(f"signed_url URL: {signed_url}")
    return signed_url

async def get_photo_url_by_filename(partial_filename: str) -> Optional[str]:
    file_info = await get_cached_file_list()
    if not file_info:
        logger.error("No file info available in cache.")
        return None

    closest_match = None
    closest_match_len_difference = float('inf')

    # Search for the closest match based on the partial filename
    for filename in file_info.keys():
        # Check if the partial filename is part of the actual filename
        if partial_filename in filename:
            # Calculate the difference in length between the search term and the candidate filename
            len_difference = len(filename) - len(partial_filename)
            
            # Update the closest match if this filename is a closer match
            if len_difference < closest_match_len_difference:
                closest_match = filename
                closest_match_len_difference = len_difference

    # If a match was found, use it
    if closest_match:
        logger.info(f"(Matched filename: {closest_match})")
        
        # URL-encode the filename to ensure it's safely included in the URL
        from urllib.parse import quote
        encoded_filename = quote(closest_match)
        
        # Construct the final URL
        final_url = f"{HOST_URL}/get-image/{encoded_filename}"
        logger.info(f"(final_url: {final_url})")
        return final_url
    else:
        logger.error(f"No filename containing '{partial_filename}' was found in cache.")
        return None



async def generate_photo_from_text(text: str) -> Optional[str]:
    try:
        logger.info(f"Generating photo filename from text: {text}")
        file_name = await get_photo_filename(text)
        if file_name:
            logger.info(f"File name generated: {file_name}")
            temp_file_path = await get_image(file_name)
            return temp_file_path
        else:
            logger.error("No file name returned from get_photo_filename")
    except Exception as e:
        logger.error(f"Failed to generate photo from text: {e}")
    return None

async def get_image(file_name: str):

    # Clean up old files in the temp directory before proceeding
    cleanup_old_temp_files()
    
    ensure_temp_dir_exists()
    temp_file_path = os.path.join(TEMP_DIR, str(uuid4()) + "-" + os.path.basename(file_name))

    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
    file_name_prefix = file_name
    valid_duration_in_seconds = 3600
    b2_authorization_token = bucket.get_download_authorization(file_name_prefix, valid_duration_in_seconds)

    b2_file_url = f"https://f005.backblazeb2.com/file/{B2_BUCKET_NAME}/{file_name}"
    headers = {"Authorization": b2_authorization_token}

    content_type = "image/jpeg"  # Default to JPEG; adjust as needed
    if file_name.lower().endswith(".png"):
        content_type = "image/png"
    elif file_name.lower().endswith(".gif"):
        content_type = "image/gif"

    async with httpx.AsyncClient() as client:
        response = await client.get(b2_file_url, headers=headers)

        if response.status_code == 200:
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(response.content)
            
            # Redirect or serve the file directly here
            return temp_file_path
        else:
            raise HTTPException(status_code=404, detail="File not found or access denied.")

def ensure_temp_dir_exists():
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

def cleanup_old_temp_files():
    now = datetime.now()
    threshold = timedelta(seconds=60)  # Files older than this will be deleted

    for filename in os.listdir(TEMP_DIR):
        file_path = os.path.join(TEMP_DIR, filename)
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        if now - file_mod_time > threshold:
            try:
                os.remove(file_path)
                logger.info(f"Deleted old temp file: {filename}")
            except Exception as e:
                logger.error(f"Failed to delete old temp file: {filename}. Error: {e}")


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




# Function to generate a signed URL
async def generate_signed_url_bkp(file_id: str) -> Optional[str]:
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


async def get_photo_url_by_filename_BKP(partial_filename: str) -> Optional[str]:
    file_info = await get_cached_file_list()
    if not file_info:
        logger.error("No file info available in cache.")
        return None

    closest_match = None
    closest_match_len_difference = float('inf')

    # Search for the closest match based on the partial filename
    for filename in file_info.keys():
        # Check if the partial filename is part of the actual filename
        if partial_filename in filename:
            # Calculate the difference in length between the search term and the candidate filename
            len_difference = len(filename) - len(partial_filename)
            
            # Update the closest match if this filename is a closer match
            if len_difference < closest_match_len_difference:
                closest_match = filename
                closest_match_len_difference = len_difference

    # If a match was found, use it
    if closest_match:
        file_id = file_info[closest_match]
        logger.info(f"Selected file ID for closest match to '{partial_filename}': {file_id} (Matched filename: {closest_match})")
        
        # Generate and return the signed URL for the found file ID
        return await generate_signed_url(file_id)
    else:
        logger.error(f"No filename containing '{partial_filename}' was found in cache.")
        return None
