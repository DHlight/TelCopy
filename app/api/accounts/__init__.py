from fastapi import APIRouter
from .accounts import router as accounts_router

router = APIRouter()

router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
