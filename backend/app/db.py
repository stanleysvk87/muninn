import sqlite3
import threading
from pathlib import Path

from .config import settings

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_lock = threading.RLock()
_connection: sqlite3.Connection | None = None


def _new_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_PATH.read_text())
    return conn


def get_db() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        with _lock:
            if _connection is None:
                _connection = _new_connection()
    return _connection


def execute(query: str, params: tuple = ()) -> sqlite3.Cursor:
    with _lock:
        db = get_db()
        cur = db.execute(query, params)
        db.commit()
        return cur
