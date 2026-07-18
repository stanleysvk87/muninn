from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .security import SESSION_COOKIE_NAME, get_session, verify_csrf

PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/bootstrap"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api") or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        token = request.cookies.get(SESSION_COOKIE_NAME)
        session = get_session(token) if token else None
        if session is None:
            return JSONResponse({"detail": "Neprihlásený"}, status_code=401)

        if request.method in UNSAFE_METHODS:
            header_value = request.headers.get("x-csrf-token")
            if not verify_csrf(token, header_value):
                return JSONResponse({"detail": "Neplatný CSRF token"}, status_code=403)

        request.state.user = session
        return await call_next(request)
