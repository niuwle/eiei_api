from b2sdk.v1 import InMemoryAccountInfo, B2Api
from app.config import B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME
import logging
from datetime import datetime, timedelta
import asyncio

# Set up logging
logger = logging.getLogger(__name__)

# Cache structure
cache = {
    "file_info": {},  # Changed to a dictionary to map file paths to URLs
    "last_update": datetime.min
}

# Cache expiration time
CACHE_EXPIRATION = timedelta(hours=1)  # Example: 1 hour

async def refresh_file_list():
    # B2 Authentication and Setup
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    # Initialize an empty dictionary to store file paths and their URLs
    file_info = {}

    # Fetch file list from B2 bucket
    for file_version, _ in bucket.ls(show_versions=False):
        # Generate the full URL for each file
        file_url = b2_api.get_download_url_for_fileid(file_version.id_)
        # Map the file path to its download URL
        file_info[file_version.file_name] = file_url

    logger.info(f"Refreshed file info from B2: {file_info}")
    return file_info

async def get_cached_file_list():
    now = datetime.now()
    if not cache["file_info"] or now - cache["last_update"] > CACHE_EXPIRATION:
        logger.info("Cache miss, refreshing...")
        cache["file_info"] = await refresh_file_list()
        cache["last_update"] = now
    else:
        logger.info("Cache hit")
    return cache["file_info"]