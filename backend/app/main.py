import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

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


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/assets/"):
            # Vite content-hashes these filenames — safe to cache forever.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif not path.startswith("/api"):
            response.headers["Cache-Control"] = "no-cache"
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
# so security/cache headers (outermost) are added last, auth (innermost,
# closest to the route) is added first.
app.add_middleware(AuthMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CacheControlMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(api_router)

# Single-process deployment: FastAPI serves the built frontend directly
# (StaticFiles + SPA fallback) — no nginx/Caddy needed, see
# docs/adr/0002-single-process-no-reverse-proxy.md. No-op if frontend/dist
# hasn't been built yet (e.g. during backend-only dev).
if settings.frontend_dist_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=settings.frontend_dist_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = settings.frontend_dist_dir / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(settings.frontend_dist_dir / "index.html")


@app.on_event("startup")
async def _startup() -> None:
    sync_watch_folders()
    asyncio.create_task(mail_ingest.run_forever())


@app.on_event("shutdown")
async def _shutdown() -> None:
    stop_watch_folders()
