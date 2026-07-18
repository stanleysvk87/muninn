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
    "expiry_dismissed_at": "TEXT",
    "review_status": "TEXT NOT NULL DEFAULT 'na_kontrolu'",
    "evidence_json": "TEXT",
    "expiry_notified_at": "TEXT",
    "notify_recurrence": "TEXT",
    "next_recurrence_at": "TEXT",
    "full_text": "TEXT",
}

_FTS_REBUILD_SQL = """
    DROP TRIGGER IF EXISTS documents_ai;
    DROP TRIGGER IF EXISTS documents_ad;
    DROP TRIGGER IF EXISTS documents_au;
    DROP TABLE IF EXISTS documents_fts;

    CREATE VIRTUAL TABLE documents_fts USING fts5(
        correspondent,
        doc_type,
        summary,
        original_filename,
        full_text,
        content='documents',
        content_rowid='id'
    );

    CREATE TRIGGER documents_ai AFTER INSERT ON documents BEGIN
        INSERT INTO documents_fts(rowid, correspondent, doc_type, summary, original_filename, full_text)
        VALUES (new.id, new.correspondent, new.doc_type, new.summary, new.original_filename, new.full_text);
    END;
    CREATE TRIGGER documents_ad AFTER DELETE ON documents BEGIN
        INSERT INTO documents_fts(documents_fts, rowid, correspondent, doc_type, summary, original_filename, full_text)
        VALUES ('delete', old.id, old.correspondent, old.doc_type, old.summary, old.original_filename, old.full_text);
    END;
    CREATE TRIGGER documents_au AFTER UPDATE ON documents BEGIN
        INSERT INTO documents_fts(documents_fts, rowid, correspondent, doc_type, summary, original_filename, full_text)
        VALUES ('delete', old.id, old.correspondent, old.doc_type, old.summary, old.original_filename, old.full_text);
        INSERT INTO documents_fts(rowid, correspondent, doc_type, summary, original_filename, full_text)
        VALUES (new.id, new.correspondent, new.doc_type, new.summary, new.original_filename, new.full_text);
    END;

    INSERT INTO documents_fts(documents_fts) VALUES('rebuild');
"""

_DEFAULT_SAVED_VIEWS = {
    "review": {
        "label": "Na kontrolu",
        "description": "Dokumenty, ktore este treba pozriet alebo rozhodnut.",
        "query": '{"review_status":"na_kontrolu"}',
        "sort_order": 10,
    },
    "pay": {
        "label": "Zaplatit",
        "description": "Faktury alebo platby oznacene na vybavenie.",
        "query": '{"review_status":"zaplatit"}',
        "sort_order": 20,
    },
    "expiring": {
        "label": "Expiracie",
        "description": "Aktivne dokumenty s datumom expiracie alebo obnovy.",
        "query": '{"expiring":true}',
        "sort_order": 30,
    },
    "failed": {
        "label": "Zlyhania",
        "description": "Subory, ktore nepresli spracovanim.",
        "query": '{"status":"failed"}',
        "sort_order": 40,
    },
    "duplicates": {
        "label": "Mozne duplikaty",
        "description": "Dokumenty s otvorenym duplikatovym warningom.",
        "query": '{"duplicates":true}',
        "sort_order": 50,
    },
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_review_status ON documents(review_status)")

    # FTS5 virtual tables can't get a column added via ALTER TABLE -- if
    # documents_fts doesn't exist yet (fresh DB) or predates full_text (an
    # existing production index), drop and recreate it against the now-
    # guaranteed-to-exist full_text column, then rebuild its contents.
    fts_columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents_fts)")}
    if "full_text" not in fts_columns:
        conn.executescript(_FTS_REBUILD_SQL)
    now = "datetime('now')"
    for key, view in _DEFAULT_SAVED_VIEWS.items():
        conn.execute(
            f"""INSERT OR IGNORE INTO saved_views
                 (key, label, description, query_json, sort_order, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, {now}, {now})""",
            (key, view["label"], view["description"], view["query"], view["sort_order"]),
        )
    conn.execute(
        """INSERT INTO document_events
             (document_id, event_type, message, actor, metadata_json, created_at)
           SELECT id, 'history_backfill',
                  'Dokument bol v DB pred zapnutim audit timeline',
                  'system', NULL, created_at
           FROM documents
           WHERE NOT EXISTS (
               SELECT 1 FROM document_events WHERE document_events.document_id = documents.id
           )"""
    )
    conn.execute(
        """INSERT INTO ingest_jobs
             (document_id, source, source_detail, original_filename, status, duplicate,
              ai_provider, error_message, started_at, finished_at)
           SELECT id, source, source_detail, original_filename, 'imported', 0,
                  ai_provider, error_message, created_at, updated_at
           FROM documents
           WHERE NOT EXISTS (
               SELECT 1 FROM ingest_jobs WHERE ingest_jobs.document_id = documents.id
           )"""
    )
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
