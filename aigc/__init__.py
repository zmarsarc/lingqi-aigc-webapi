from fastapi import APIRouter
from . import wx_callback


router = APIRouter(prefix="/api")

router.include_router(wx_callback.router)