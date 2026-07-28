"""Test environment setup. Must run before any `app.*` module is imported
anywhere (including by other test files), since app.config.Settings() reads
these environment variables once at import time and caches the resulting
paths/db connection as module-level singletons."""

import os
import shutil
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="muninn-test-"))
(_TMP_ROOT / "data").mkdir()
(_TMP_ROOT / "archive").mkdir()

os.environ["MUNINN_DATA_DIR"] = str(_TMP_ROOT / "data")
os.environ["MUNINN_ARCHIVE_DIR"] = str(_TMP_ROOT / "archive")
os.environ["MUNINN_DB_PATH"] = str(_TMP_ROOT / "data" / "muninn.db")
os.environ["MUNINN_FRONTEND_DIST_DIR"] = str(_TMP_ROOT / "no-frontend-dist")
os.environ["MUNINN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["MUNINN_COOKIE_SECURE"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import throttle  # noqa: E402
from app.auth.security import bootstrap_token  # noqa: E402
from app.db import execute  # noqa: E402
from app.main import app  # noqa: E402


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)


@pytest.fixture(scope="session")
def client():
    # Not using `with TestClient(app)` deliberately: that would trigger the
    # startup event and spin up the mail/expiry/queue-retry background
    # loops as real asyncio tasks for the whole test session. Routes are
    # registered at import time regardless, so the app works fine for
    # request/response testing without running its lifespan.
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_tables():
    """Every test starts with an empty documents table (and everything that
    references it) -- tests share one on-disk SQLite database for the whole
    session rather than each getting a fresh file, so this is what keeps
    them from seeing each other's rows."""
    yield
    # Login throttling counters are process-global, so one test's failed
    # login attempts must not lock out the next test's fixture login.
    throttle.clear_all()
    for table in (
        "document_duplicate_candidates",
        "document_events",
        "ingest_jobs",
        "documents",
    ):
        execute(f"DELETE FROM {table}")


@pytest.fixture
def admin_session(client):
    """Bootstrap (or reuse) the admin account and return cookies for an
    authenticated session."""
    client.cookies.clear()
    res = client.post(
        "/api/auth/bootstrap",
        json={
            "username": "admin",
            "password": "test-password-123",
            "consent": True,
            # Creating the first account requires the host-side setup token
            # (see app/auth/security.bootstrap_token).
            "setup_token": bootstrap_token(),
        },
    )
    if res.status_code == 409:
        res = client.post(
            "/api/auth/login", json={"username": "admin", "password": "test-password-123"}
        )
    assert res.status_code == 200, res.text
    return client.cookies


@pytest.fixture
def csrf_headers(client, admin_session):
    """Header dict for state-changing (POST/PUT/PATCH/DELETE) requests --
    AuthMiddleware requires X-CSRF-Token to match the session's csrf_secret,
    double-submit style, for anything other than GET."""
    return {"X-CSRF-Token": client.cookies.get("muninn_csrf")}
