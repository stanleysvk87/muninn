# ADR 0001: SQLite + FTS5 instead of a flat JSON store

## Context

Heimdall (`/opt/heimdall`), the closest existing pattern in this homelab,
uses no database — it persists to `app/data/*.json` via an atomic-write
helper (`core/json_store.py`). That works well for dashboards and
configuration, where you read/write by a known key.

Muninn needs something different: full-text search across a growing
archive of documents ("find everything from Uniqa"), which flat JSON
files can't offer without writing a search engine from scratch.

## Decision

Use SQLite with an FTS5 virtual table (`documents_fts`), kept in sync via
triggers on the main `documents` table. `users`, `sessions`, and
`settings` go into the same SQLite database — one file, not a mix of
SQLite and JSON.

## Consequences

- Still a single file, no extra service (no Postgres/Elasticsearch),
  equally portable as Heimdall's approach.
- FTS5 ships as part of Python's standard `sqlite3` library (verified on
  this host) — no new system dependency.
- The deviation from house convention is deliberate and local to this
  project — it doesn't change anything about Heimdall or elsewhere.
