# app/utils/file_list_cache.py
import logging
from datetime import datetime, timedelta
from b2sdk.v1 import InMemoryAccountInfo, B2Api
from app.config import B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME

# Set up logging
logger = logging.getLogger(__name__)

# Cache structure
cache = {
    "file_info": {},  # Now maps file paths to file IDs
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

    # Initialize an empty dictionary to store file paths and their file IDs
    file_info = {}

    # Fetch file list from B2 bucket
    for file_version, _ in bucket.ls(show_versions=False, recursive=True):
        # Instead of generating a URL, store the file ID
        file_info[file_version.file_name] = file_version.id_

    logger.info("Refreshed file info from B2.")
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