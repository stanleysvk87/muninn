import sqlite3
import threading
from pathlib import Path

from .config import settings

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_lock = threading.RLock()
_connection: sqlite3.Connection | None = None


_DOCUMENTS_COLUMNS = {
    "cost_usd": "REAL",
    "input_tokens": "INTEGER",
    "output_tokens": "INTEGER",
    "expiry_date": "TEXT",
}


def _migrate(conn: sqlite3.Connection) -> None:
    """CREATE TABLE IF NOT EXISTS in schema.sql only handles brand-new
    databases -- columns added after a table already exists on disk (e.g. in
    the production volume) need an explicit ALTER TABLE."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
    for column, coltype in _DOCUMENTS_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {column} {coltype}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_expiry_date ON documents(expiry_date)")
    conn.commit()


def _new_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_PATH.read_text())
    _migrate(conn)
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
