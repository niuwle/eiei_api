#./app/routers/get_image.py
from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from b2sdk.v1 import InMemoryAccountInfo, B2Api
from app.config import B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME
import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add a new route for serving images through the proxy
router = APIRouter()

@router.get("/get-image/{file_name:path}")  # Note the :path suffix here
async def get_image(file_name: str):
    logger.info(f"Requesting file: {file_name}")

    # Preliminary checks and validations can be added here
    # For example, ensure the file_name is safe to use in a request

    # Use your existing B2 API client setup to get the authorization token
    # This is a simplified example; you'll need to adjust it based on your actual B2 client setup
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY)
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)

    # Assuming you have a function to get the download authorization token for a file
    # The file_name_prefix could be the file name or a directory prefix
    file_name_prefix = file_name  # Adjust as necessary
    valid_duration_in_seconds = 3600  # Example: 1 hour
    b2_authorization_token = bucket.get_download_authorization(file_name_prefix, valid_duration_in_seconds)

    # Construct the B2 URL for the file
    b2_file_url = f"https://f005.backblazeb2.com/file/{B2_BUCKET_NAME}/{file_name}"

    logger.info(f"Rb2_file_url: {b2_file_url}")
    logger.info(f"b2_authorization_token: {b2_authorization_token}")
    # Fetch the file from B2
    headers = {"Authorization": b2_authorization_token}

    async with httpx.AsyncClient() as client:
        response = await client.get(b2_file_url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            # Stream the file content back to the client
            return StreamingResponse(response.iter_bytes(), media_type=response.headers["Content-Type"])
        else:
            # Handle errors or file not found
            raise HTTPException(status_code=404, detail="File not found or access denied.")
