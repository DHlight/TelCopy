from fastapi import APIRouter
from .messages import router as messages_router

router = APIRouter()

router.include_router(messages_router, prefix="/messages", tags=["messages"])
