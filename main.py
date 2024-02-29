from fastapi import FastAPI, Depends
from app.controllers import router as api_router
from app.routers.telegram_webhook import router as telegram_router
from app.routers.get_image import router as get_image_router
from app.logging_config import setup_logging
from fastapi.staticfiles import StaticFiles
import asyncio
from app.utils.file_list_cache import get_cached_file_list

from app.controllers.ai_communication import get_photo_filename
setup_logging()
app = FastAPI()

import logging

logger = logging.getLogger(__name__)
# Include routers
app.include_router(api_router)
app.include_router(telegram_router)
app.include_router(get_image_router)

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    # Refresh the file list cache when the application starts
    file_list = await get_cached_file_list()
    # Print the refreshed file list
    logger.info("Cache initialized with the following files:")
    
    # for file_url in file_list:
    #     logger.info(file_url)
# 
    # logger.info("test function "+await get_photo_filename("show me a red car"))