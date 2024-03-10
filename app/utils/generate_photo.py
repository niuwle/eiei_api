# app/utils/generate_photo.py
import httpx
import random
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
import re
import shutil
from fastapi import APIRouter, HTTPException, BackgroundTasks

TEMP_DIR = "./temp_files"  # Temporary storage directory

# Set up logging
logger = logging.getLogger(__name__)



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

async def get_image(partial_filename: str):

    ensure_temp_dir_exists()
    # Clean up old files in the temp directory before proceeding
    cleanup_old_temp_files()

    file_info = await get_cached_file_list()
    if not file_info:
        logger.error("No file info available in cache.")
        return None

    closest_match = None
    closest_match_len_difference = float('inf')

    # Search for the closest match based on the partial filename
    #for filename in file_info.keys():
    #    # Check if the partial filename is part of the actual filename
    #    if partial_filename in filename:
    #        # Calculate the difference in length between the search term and the candidate filename
    #        len_difference = len(filename) - len(partial_filename)
    #        
    #        # Update the closest match if this filename is a closer match
    #        if len_difference < closest_match_len_difference:
    #            closest_match = filename
    #            closest_match_len_difference = len_difference
#
    closest_match = find_best_match(file_info.keys(), partial_filename)

    # If a match was found, use it
    if closest_match:
        logger.info(f"(Matched filename: {closest_match})")

        temp_file_path = os.path.join(TEMP_DIR, str(uuid4()) + "-" + os.path.basename(closest_match))


        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account("production", B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY)
        bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
        file_name_prefix = closest_match
        valid_duration_in_seconds = 3600
        b2_authorization_token = bucket.get_download_authorization(file_name_prefix, valid_duration_in_seconds)

        b2_file_url = f"https://f005.backblazeb2.com/file/{B2_BUCKET_NAME}/{closest_match}"
        headers = {"Authorization": b2_authorization_token}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(b2_file_url, headers=headers)

            if response.status_code == 200:
                with open(temp_file_path, "wb") as temp_file:
                    temp_file.write(response.content)
                
                # Redirect or serve the file directly here
                return temp_file_path
            else:
                raise HTTPException(status_code=404, detail="File not found or access denied.")

    else:
        logger.error(f"No filename containing '{partial_filename}' was found in cache.")
        return None


def ensure_temp_dir_exists():
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

def cleanup_old_temp_files():
    now = datetime.utcnow()
    threshold = timedelta(seconds=60)  # Files older than this will be deleted

    for filename in os.listdir(TEMP_DIR):
        file_path = os.path.join(TEMP_DIR, filename)
        file_mod_time = datetime.utcfromtimestamp(os.path.getmtime(file_path))
        if now - file_mod_time > threshold:
            try:
                os.remove(file_path)
                logger.info(f"Deleted old temp file: {filename}")
            except Exception as e:
                logger.error(f"Failed to delete old temp file: {filename}. Error: {e}")



def find_best_match(filenames, search_key):
    """
    Search for the best match for a given search key among a list of filenames.
    Incorporates multiple strategies such as exact match, regex, prefix/suffix, and simplified fuzzy matching,
    returning the top match as a string along with debug information.

    :param filenames: An iterable of filenames to search through.
    :param search_key: The search key to find matches for.
    :return: Tuple of the best match filename as a string and debugging information.
    """
    debug_info = []

    # Ensure filenames is a list to avoid issues with non-reiterable iterables
    if not isinstance(filenames, list):
        filenames = list(filenames)

    # Guard against empty search_key or filenames
    if not search_key or not filenames:
        debug_info.append("Empty search_key or filenames provided.")
        return "", debug_info

    # Exact match
    for filename in filenames:
        if filename == search_key:
            debug_info.append(f"Exact match found: {filename}")
            return filename, debug_info

    # Improved regex match
    search_key_escaped = re.escape(search_key)
    for filename in filenames:
        if re.search(search_key_escaped, filename):
            debug_info.append(f"Regex match found: {filename}")
            return filename, debug_info

    # Prefix/Suffix match
    normalized_search_key = search_key.replace('\\', '/')
    for filename in filenames:
        normalized_filename = filename.replace('\\', '/')
        if normalized_filename.startswith(normalized_search_key) or normalized_filename.endswith(normalized_search_key):
            debug_info.append(f"Prefix/Suffix match found: {filename}")
            return filename, debug_info

    # Simplified fuzzy match as last resort
    for filename in filenames:
        if simplified_fuzzy_match(search_key, filename):
            debug_info.append(f"Fuzzy match found: {filename}")
            return filename, debug_info

    # No matches found
    debug_info.append("No matches found. Returning a random filename as fallback.")
    fallback = random.choice(filenames)
    return fallback, debug_info

def simplified_fuzzy_match(search_key, filename):
    """
    Perform a simplified fuzzy match between the search key and the filename.
    Counts the number of matching characters, allowing for some mismatches.

    :param search_key: The search key to match.
    :param filename: The filename to compare against the search key.
    :return: Boolean indicating if a fuzzy match is found.
    """
    match_score = sum(char in filename for char in search_key)
    tolerance = len(search_key) * 0.6
    return match_score >= tolerance