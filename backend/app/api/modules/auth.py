from fastapi import APIRouter, Request, Response

from ...auth import throttle
from ...auth.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    burn_password_time,
    consume_bootstrap_token,
    create_session,
    create_user,
    delete_session,
    get_user_by_username,
    users_exist,
    verify_bootstrap_token,
    verify_password,
)
from ...config import settings
from ...errors import api_error

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _throttle_keys(request: Request, username: str) -> list[str]:
    keys = [f"ip:{_client_ip(request)}"]
    if username:
        keys.append(f"user:{username.lower()}")
    return keys


def _set_session_cookies(response: Response, token: str, csrf_secret: str) -> None:
    max_age = settings.session_ttl_days * 24 * 3600
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    # CSRF cookie must be readable by JS (not httponly) so the frontend can echo it back as a header.
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_secret,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/bootstrap")
def bootstrap(payload: dict, response: Response, request: Request):
    if users_exist():
        raise api_error(409, "admin_already_exists")

    keys = [f"ip:{_client_ip(request)}", "bootstrap"]
    wait = throttle.retry_after(keys)
    if wait is not None:
        raise api_error(429, "too_many_attempts", seconds=wait)

    # Creating the first admin account is not first-come-first-served any
    # more: it requires the token generated on the host (see
    # auth/security.bootstrap_token). Checked before anything else so a
    # remote caller cannot even probe usernames through this endpoint.
    if not verify_bootstrap_token(payload.get("setup_token")):
        throttle.record_failure(keys)
        raise api_error(403, "bootstrap_token_invalid")

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or len(password) < 8:
        raise api_error(422, "username_password_required")
    if not payload.get("consent"):
        raise api_error(422, "consent_required")
    user_id = create_user(username, password, consented=True)
    consume_bootstrap_token()
    throttle.reset(keys)
    token, csrf_secret, _ = create_session(user_id, request.headers.get("user-agent", ""), _client_ip(request))
    _set_session_cookies(response, token, csrf_secret)
    return {"username": username}


@router.post("/login")
def login(payload: dict, response: Response, request: Request):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    keys = _throttle_keys(request, username)
    wait = throttle.retry_after(keys)
    if wait is not None:
        # Refused before the KDF runs: unlimited attempts were both a
        # guessing oracle and a CPU amplifier (200k PBKDF2 rounds per try).
        raise api_error(429, "too_many_attempts", seconds=wait)

    user = get_user_by_username(username)
    if user is None:
        # Equalise the response time with the real path -- see
        # auth/security.burn_password_time.
        burn_password_time(password)
        throttle.record_failure(keys)
        raise api_error(401, "invalid_credentials")
    if not verify_password(password, user["password_hash"], user["password_salt"]):
        throttle.record_failure(keys)
        raise api_error(401, "invalid_credentials")

    throttle.reset(keys)
    token, csrf_secret, _ = create_session(user["id"], request.headers.get("user-agent", ""), _client_ip(request))
    _set_session_cookies(response, token, csrf_secret)
    return {"username": user["username"]}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        delete_session(token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise api_error(401, "not_authenticated")
    return {"username": user["username"], "role": user["user_role"]}
