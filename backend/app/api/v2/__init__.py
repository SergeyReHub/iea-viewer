from fastapi import APIRouter

from app.api.v2 import sources
from app.api.v2.router import v2_router

router = APIRouter()
router.include_router(sources.router)
router.include_router(v2_router)
