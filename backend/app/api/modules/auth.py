from fastapi import APIRouter, HTTPException, Request, Response

from ...auth.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    create_session,
    create_user,
    delete_session,
    get_user_by_username,
    users_exist,
    verify_password,
)
from ...config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


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
        raise HTTPException(status_code=409, detail="Admin účet už existuje")
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or len(password) < 8:
        raise HTTPException(status_code=422, detail="Používateľské meno a heslo (min. 8 znakov) sú povinné")
    user_id = create_user(username, password)
    token, csrf_secret, _ = create_session(user_id, request.headers.get("user-agent", ""), request.client.host if request.client else "")
    _set_session_cookies(response, token, csrf_secret)
    return {"username": username}


@router.post("/login")
def login(payload: dict, response: Response, request: Request):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    user = get_user_by_username(username)
    if user is None or not verify_password(password, user["password_hash"], user["password_salt"]):
        raise HTTPException(status_code=401, detail="Nesprávne meno alebo heslo")
    token, csrf_secret, _ = create_session(user["id"], request.headers.get("user-agent", ""), request.client.host if request.client else "")
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
        raise HTTPException(status_code=401, detail="Neprihlásený")
    return {"username": user["username"], "role": user["user_role"]}
