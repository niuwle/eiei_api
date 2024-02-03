# app/main.py
from fastapi import FastAPI
from app.controllers import router as api_router
# from app.routers.message_controller import router as message_router
from app.routers.telegram_webhook import router as telegram_router
from app.logging_config import setup_logging

setup_logging()
app = FastAPI()

# Include routers
app.include_router(api_router)
# app.include_router(message_router)
app.include_router(telegram_router)

