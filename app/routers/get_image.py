#./app/routers/get_image.py
import os
import shutil
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from b2sdk.v1 import InMemoryAccountInfo, B2Api
from app.config import B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME
import httpx
import logging
from uuid import uuid4
import time
TEMP_DIR = "./temp_files"  # Temporary storage directory

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

def ensure_temp_dir_exists():
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

@router.get("/get-image/{file_name:path}")
async def get_image(background_tasks: BackgroundTasks, file_name: str):
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
            
            # Schedule the cleanup task to run after sending the response
            background_tasks.add_task(delete_temp_file, temp_file_path, delay=60)
            
            # Redirect or serve the file directly here
            return FileResponse(path=temp_file_path, media_type=content_type, filename=file_name)
        else:
            raise HTTPException(status_code=404, detail="File not found or access denied.")

def delete_temp_file(file_path: str, delay: int):
    """Deletes the specified file after a delay."""
    time.sleep(delay)  # Delay before deletion
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Deleted temp file: {file_path}")
    else:
        logger.error(f"File not found for deletion: {file_path}")