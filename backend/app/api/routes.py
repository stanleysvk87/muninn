from fastapi import APIRouter

from .modules import register_api_modules

router = APIRouter(prefix="/api")
register_api_modules(router)
