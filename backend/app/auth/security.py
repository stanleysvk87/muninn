import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..db import execute

logger = logging.getLogger("muninn.auth")

SESSION_COOKIE_NAME = "muninn_session"
CSRF_COOKIE_NAME = "muninn_csrf"
PBKDF2_ITERATIONS = 200_000
BOOTSTRAP_TOKEN_FILENAME = "bootstrap-token.txt"

# Salt for the decoy hash below. Random per process on purpose -- it never
# has to verify against anything, it only has to cost the same as a real one.
_DECOY_SALT = secrets.token_hex(16)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    candidate, _ = hash_password(password, password_salt)
    return secrets.compare_digest(candidate, password_hash)


def burn_password_time(password: str) -> None:
    """Spend the same ~0.11 s of PBKDF2 a real verification costs.

    /api/auth/login used to return "invalid credentials" for an unknown
    username *before* doing any key derivation, so an unknown user answered
    in ~1 ms and a known one in ~110 ms: a trivially measurable oracle for
    enumerating which accounts exist. Called on the unknown-user path so both
    branches cost the same."""
    hash_password(password, _DECOY_SALT)


def bootstrap_token() -> str:
    """Token required to create the very first admin account.

    /api/auth/bootstrap has to be reachable without a session (there is no
    account yet), and it used to be pure first-come-first-served: anyone who
    reached the app during the window before the owner registered -- a fresh
    deploy, or a restore onto an empty muninn.db -- got the admin account and
    with it the entire document archive. The token closes that window: it is
    generated on the host the app runs on, readable only by the app's own
    user, and consumed once the account exists.

    Set MUNINN_BOOTSTRAP_TOKEN to pin it explicitly (e.g. in an automated
    deploy); otherwise it is generated into data_dir/bootstrap-token.txt.
    """
    if settings.bootstrap_token:
        return settings.bootstrap_token

    path = settings.data_dir / BOOTSTRAP_TOKEN_FILENAME
    if path.is_file():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    token = secrets.token_urlsafe(24)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        logger.warning("Nepodarilo sa nastavit prava 0600 na %s", path)
    logger.warning(
        "Ziadny pouzivatel neexistuje. Token pre vytvorenie admin uctu je v %s", path
    )
    return token


def verify_bootstrap_token(candidate: str | None) -> bool:
    return bool(candidate) and secrets.compare_digest(candidate, bootstrap_token())


def consume_bootstrap_token() -> None:
    """The token is single-use: once an admin account exists, bootstrap is a
    409 anyway, so leaving the file around only risks it being copied."""
    path = settings.data_dir / BOOTSTRAP_TOKEN_FILENAME
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Nepodarilo sa zmazat bootstrap token %s", path)


def users_exist() -> bool:
    row = execute("SELECT COUNT(*) AS c FROM users").fetchone()
    return row["c"] > 0


def create_user(username: str, password: str, role: str = "admin", consented: bool = False) -> int:
    password_hash, password_salt = hash_password(password)
    now = _now_iso()
    cur = execute(
        """INSERT INTO users (username, password_hash, password_salt, role, created_at, consented_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (username, password_hash, password_salt, role, now, now if consented else None),
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
