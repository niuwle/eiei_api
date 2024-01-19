# app/main.py
from fastapi import FastAPI
from app.controllers import router as api_router
from app.routers.message_controller import router as message_router
from app.scheduler import setup_scheduler
from app.logging_config import setup_logging

setup_logging()
app = FastAPI()

# Include routers
app.include_router(api_router)
app.include_router(message_router)

# Setup scheduler after FastAPI app creation
setup_scheduler()
