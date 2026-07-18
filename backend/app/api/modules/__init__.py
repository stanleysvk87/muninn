from fastapi import APIRouter

from . import auth, health


def register_api_modules(router: APIRouter) -> None:
    router.include_router(health.router)
    router.include_router(auth.router)
