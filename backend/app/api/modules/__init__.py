from fastapi import APIRouter

from . import auth, documents, health, settings, upload


def register_api_modules(router: APIRouter) -> None:
    router.include_router(health.router)
    router.include_router(auth.router)
    router.include_router(upload.router)
    router.include_router(documents.router)
    router.include_router(settings.router)
