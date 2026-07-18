import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .api.routes import router as api_router
from .auth.middleware import AuthMiddleware
from .config import settings
from .ingest import mail_ingest
from .ingest.watch_folder import stop_all as stop_watch_folders
from .ingest.watch_folder import sync_watch_folders

app = FastAPI(title="Muninn")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Middleware order matters: Starlette applies these in reverse of add order,
# so security headers (outermost) are added last, auth (innermost, closest to
# the route) is added first.
app.add_middleware(AuthMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(api_router)

# Frontend static-file serving (SPA fallback, GZip, cache headers) is added
# in Phase 5 once frontend/dist exists — see docs ARCHITECTURE.md.


@app.on_event("startup")
async def _startup() -> None:
    sync_watch_folders()
    asyncio.create_task(mail_ingest.run_forever())


@app.on_event("shutdown")
async def _shutdown() -> None:
    stop_watch_folders()
