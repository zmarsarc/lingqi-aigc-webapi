from fastapi import APIRouter
from . import async_infer

router = APIRouter()
router.include_router(async_infer.router)
