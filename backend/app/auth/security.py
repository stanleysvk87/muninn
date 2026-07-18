import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..db import execute

SESSION_COOKIE_NAME = "muninn_session"
CSRF_COOKIE_NAME = "muninn_csrf"
PBKDF2_ITERATIONS = 200_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    candidate, _ = hash_password(password, password_salt)
    return secrets.compare_digest(candidate, password_hash)


def users_exist() -> bool:
    row = execute("SELECT COUNT(*) AS c FROM users").fetchone()
    return row["c"] > 0


def create_user(username: str, password: str, role: str = "admin") -> int:
    password_hash, password_salt = hash_password(password)
    cur = execute(
        "INSERT INTO users (username, password_hash, password_salt, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (username, password_hash, password_salt, role, _now_iso()),
    )
    return cur.lastrowid


def get_user_by_username(username: str):
    return execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def create_session(user_id: int, user_agent: str = "", ip: str = "") -> tuple[str, str, str]:
    token = secrets.token_urlsafe(48)
    csrf_secret = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=settings.session_ttl_days)).isoformat()
    execute(
        """INSERT INTO sessions (token, user_id, csrf_secret, created_at, expires_at, last_seen_at, user_agent, ip)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (token, user_id, csrf_secret, now.isoformat(), expires_at, now.isoformat(), user_agent, ip),
    )
    execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now.isoformat(), user_id))
    return token, csrf_secret, expires_at


def get_session(token: str):
    row = execute(
        """SELECT sessions.*, users.username, users.role AS user_role
           FROM sessions JOIN users ON users.id = sessions.user_id
           WHERE sessions.token = ?""",
        (token,),
    ).fetchone()
    if row is None:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        delete_session(token)
        return None
    return row


def delete_session(token: str) -> None:
    execute("DELETE FROM sessions WHERE token = ?", (token,))


def verify_csrf(token: str, header_value: str | None) -> bool:
    if not header_value:
        return False
    session = get_session(token)
    if session is None:
        return False
    return secrets.compare_digest(header_value, session["csrf_secret"])
