from fastapi import FastAPI, Depends, Request
from fastapi.responses import PlainTextResponse
from app.controllers import router as api_router
from app.routers.telegram_webhook import router as telegram_router
from app.logging_config import setup_logging
from fastapi.staticfiles import StaticFiles
import asyncio
from app.utils.file_list_cache import get_cached_file_list
from app.utils.automatic_reply import check_and_trigger_responses
from app.routers.keep_alive import router as keep_alive_router
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.controllers.ai_communication import get_photo_filename, rate_limit_exceeded_handler

setup_logging()
app = FastAPI()

import logging

logger = logging.getLogger(__name__)
# Include routers
app.include_router(api_router)
app.include_router(telegram_router)
app.include_router(keep_alive_router)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("b2sdk").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    # Refresh the file list cache when the application starts
    file_list = await get_cached_file_list()
    # Print the refreshed file list
    logger.info("Cache initialized with the following files:")
    asyncio.create_task(check_and_trigger_responses())

# Remove the duplicate exception handler
# @app.exception_handler(RateLimitExceeded)
# async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
#     return PlainTextResponse(str(exc), status_code=429)