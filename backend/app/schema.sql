-- Muninn — SQLite schema. Jeden súbor pre všetko (users/sessions/settings/
-- documents), vedomá odchýlka od Heimdallovho flat-JSON store — pozri
-- docs/adr/0001-sqlite-fts5-instead-of-json-store.md.

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    password_salt   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'admin',
    created_at      TEXT NOT NULL,
    last_login_at   TEXT,
    consented_at    TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token           TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_secret     TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    user_agent      TEXT,
    ip              TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    original_filename   TEXT NOT NULL,
    stored_path         TEXT NOT NULL UNIQUE,
    correspondent       TEXT NOT NULL,
    doc_type            TEXT NOT NULL DEFAULT 'other',
    doc_date            TEXT,
    expiry_date         TEXT,
    expiry_dismissed_at TEXT,
    amount_value        REAL,
    amount_currency     TEXT,
    amount_raw          TEXT,
    summary             TEXT,
    summary_sk          TEXT,
    summary_en          TEXT,
    source              TEXT NOT NULL,
    source_detail       TEXT,
    ai_provider         TEXT,
    ai_model            TEXT,
    ai_raw_response     TEXT,
    mime_type           TEXT NOT NULL,
    file_size           INTEGER NOT NULL,
    file_hash           TEXT NOT NULL,
    cost_usd            REAL,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    review_status       TEXT NOT NULL DEFAULT 'na_kontrolu',
    evidence_json       TEXT,
    full_text           TEXT,
    status              TEXT NOT NULL DEFAULT 'processed',
    error_message       TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_correspondent ON documents(correspondent);
CREATE INDEX IF NOT EXISTS idx_documents_doc_date ON documents(doc_date);
-- idx_documents_expiry_date is created in db.py's _migrate(), not here --
-- this script runs unconditionally on every connection (via executescript,
-- before _migrate() has a chance to ALTER TABLE), so indexing a column
-- that doesn't exist yet on an already-existing production table would
-- crash startup before the migration ever runs.
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
-- idx_documents_review_status is created in db.py's _migrate(), for the same
-- reason as idx_documents_expiry_date above.

CREATE TABLE IF NOT EXISTS document_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    message         TEXT NOT NULL,
    actor           TEXT NOT NULL DEFAULT 'system',
    metadata_json   TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_document_events_document ON document_events(document_id, created_at DESC);

-- Deliberately NO foreign key to documents: document_events cascades away
-- with the row it belongs to, so deletion -- the one operation a GDPR trail
-- needs most, and the only irreversible one in the app -- left no trace at
-- all. This table is the surviving record of what was removed, by whom and
-- when. It intentionally keeps only identifying metadata, never the
-- document body/summary.
CREATE TABLE IF NOT EXISTS document_deletions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER NOT NULL,
    original_filename   TEXT,
    correspondent       TEXT,
    doc_type            TEXT,
    stored_path         TEXT,
    file_removed        INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT,
    actor               TEXT NOT NULL DEFAULT 'user',
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_document_deletions_created ON document_deletions(created_at DESC);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id         INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    source              TEXT NOT NULL,
    source_detail       TEXT,
    original_filename   TEXT NOT NULL,
    status              TEXT NOT NULL,
    duplicate           INTEGER NOT NULL DEFAULT 0,
    ai_provider         TEXT,
    error_message       TEXT,
    started_at          TEXT NOT NULL,
    finished_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_started ON ingest_jobs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_document ON ingest_jobs(document_id);

CREATE TABLE IF NOT EXISTS document_duplicate_candidates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    candidate_id    INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    score           REAL NOT NULL,
    reason          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(document_id, candidate_id)
);
CREATE INDEX IF NOT EXISTS idx_duplicate_candidates_document ON document_duplicate_candidates(document_id, status);

CREATE TABLE IF NOT EXISTS saved_views (
    key             TEXT PRIMARY KEY,
    label           TEXT NOT NULL,
    description     TEXT,
    query_json      TEXT NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- documents_fts (with full_text/summary_sk/summary_en) and its triggers are created in db.py's
-- _migrate() -- FTS5 virtual tables can't get a column added via ALTER
-- TABLE, so an already-existing production index needs a drop+rebuild
-- rather than a CREATE ... IF NOT EXISTS here, which would just silently
-- keep the old 4-column shape forever on an existing DB.
