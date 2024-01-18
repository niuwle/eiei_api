from fastapi import APIRouter
from .message_controller import router as message_router

router = APIRouter()

router.include_router(message_router)
