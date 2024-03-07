# app/utils/file_list_cache.py
import logging
from datetime import datetime, timedelta
from b2sdk.v1 import InMemoryAccountInfo, B2Api
from app.config import B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME
import asyncio
from b2sdk.exception import B2Error  # Import B2Error for catching Backblaze B2 specific errors

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
    
    retry_interval = 60  # Retry every 60 seconds
    max_retries = 100  # Maximum number of retries
    attempt_count = 0

    while attempt_count < max_retries:
        try:
            b2_api.authorize_account("production", B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY)
            bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

            # Initialize an empty dictionary to store file paths and their file IDs
            file_info = {}

            # Fetch file list from B2 bucket
            for file_version, _ in bucket.ls(show_versions=False, recursive=True):
                file_info[file_version.file_name] = file_version.id_

            logger.info("Refreshed file info from B2.")
            return file_info
        except B2Error as e:
            attempt_count += 1
            logger.error(f"Failed to refresh file list from B2 on attempt {attempt_count}: {e}. Retrying in {retry_interval} seconds...")
            await asyncio.sleep(retry_interval)  # Wait for retry_interval seconds before retrying

    # After max_retries, log that the operation has failed and return the existing cache if any
    logger.error(f"Failed to refresh file list from B2 after {max_retries} attempts. Will use the existing cache.")
    return cache.get("file_info", {})

async def get_cached_file_list():
    now = datetime.utcnow()
    if not cache["file_info"] or now - cache["last_update"] > CACHE_EXPIRATION:
        logger.info("Cache miss, refreshing...")
        cache["file_info"] = await refresh_file_list()
        cache["last_update"] = now
    else:
        logger.info("Cache hit")
    return cache["file_info"]