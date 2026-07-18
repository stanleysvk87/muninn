# Architecture

## Overview

One Python process (FastAPI) serves both the API and the built React
frontend. No nginx/Caddy in front — SPA fallback and gzip are handled
directly in `main.py`. Reason: the app needs to run identically as a
single Docker container or a single systemd service on any Linux host,
with no reverse-proxy dependency.

```
                    ┌─────────────────────────────┐
  photo/PDF ───────▶│  watch folder (watchdog)    │
  mail attachment ─▶│  IMAP poller (optional)     ├──▶ ingest/pipeline.py
  web upload ──────▶│  POST /api/upload           │         │
  multi-page merge ▶│  POST /api/upload/combine   │         │
                    └─────────────────────────────┘         ▼
                                                    ai_engine (claude/codex
                                                    CLI, or Anthropic API
                                                    key) with automatic
                                                    fallback + pending queue
                                                             │
                                                             ▼
                                          archive/<correspondent>/ + SQLite
                                                             │
                                                             ▼
                                    FTS5 full-text search ◀── web UI
```

Two background loops run alongside the web server: `mail_ingest.py` polls
the configured IMAP mailbox, `expiry_notifier.py` checks for upcoming
document expirations and recurring reminders and sends Telegram messages,
and `queue_retry.py` retries documents that landed in the `pending` status
(see below) once an AI provider is available again.

## Key decisions (and deviations from Heimdall)

Heimdall (`/opt/heimdall`) is the closest existing pattern in this homelab
(FastAPI + React, session-cookie auth with CSRF). Muninn reuses what makes
sense and deviates where the app's purpose requires it:

- **SQLite + FTS5 instead of flat JSON files.** Heimdall has no database,
  it persists to `app/data/*.json` via an atomic-write helper — fine for
  dashboards, but Muninn needs real full-text search across a growing
  archive, which flat JSON can't do. SQLite is still a single file, no
  extra service (no Postgres), equally portable. See
  `docs/adr/0001-sqlite-fts5-instead-of-json-store.md`.
- **Single process, no nginx/Caddy.** Heimdall runs as 3 containers
  (backend, frontend+nginx, optional Caddy). Muninn simplifies this to one
  process specifically because of the "Docker or systemd, on any Linux"
  requirement — a reverse proxy would add moving parts to the systemd
  path. See `docs/adr/0002-single-process-no-reverse-proxy.md`.
- **`watchdog` (Python library) instead of `inotifywait`.** No extra apt
  dependency in the Docker image, works identically under systemd.
- **AI extraction sandboxing.** A document can come from an external
  party (a supplier's invoice) and could contain text trying to manipulate
  the model (prompt injection). So the AI call only ever gets **read
  access to one isolated temp copy** of the single document being
  processed (never the shared inbox/watch-folder). Moving the file into
  the archive and writing to the database is always done by backend code
  based on the model's parsed JSON output — never directly by the model.

## AI provider chain and the pending queue

`ai_engine.get_provider_chain()` returns providers in this order (for
"auto" mode):

1. `claude` CLI (`~/.local/bin/claude`), if found and logged in — headless
   `claude -p`, under the existing subscription, no extra billing.
2. `codex` CLI, if `claude` isn't available.
3. An Anthropic API key entered in Settings (encrypted at rest via
   Fernet), if neither CLI is available.

`ingest/pipeline.py` tries each provider in the chain in turn. The
important distinction is *why* a provider failed:

- **`ProviderUnavailableError`** (a subclass of `ExtractionError`): the
  provider itself couldn't be reached — auth rejected, rate limited,
  timed out, binary/runtime missing. Detected via each provider's own
  signal: `claude_cli` via the API error envelope's `api_error_status`
  (401/403/429/5xx, present even on a non-zero exit code); `codex_cli` via
  known stderr substrings (auth/rate-limit/missing runtime); `anthropic_api`
  via `APIStatusError.status_code` / `APIConnectionError`.
- **Plain `ExtractionError`**: the provider genuinely tried and the
  content itself was the problem (unreadable file, garbled response, the
  `BAD_RESULT_PHRASES` check catching a technical failure disguised as a
  low-confidence answer).

If **every** provider in the chain fails with `ProviderUnavailableError`
(or none are configured at all), the document is stored with status
`pending`, not `failed` — nothing about the document was actually wrong,
there was just nobody to ask. `queue_retry.py` retries `pending` documents
every 10 minutes via `reprocess_document()`, which updates the existing
row in place instead of inserting a new one (unlike `process()`, which is
for first-time ingest). If a genuine content-level failure occurs on
retry, the document correctly moves to `failed` instead of retrying
forever. The same `reprocess_document()` backs the manual "Retry" button
in Settings.

A critical CLI-invocation detail, discovered the hard way for both CLIs:
the prompt argument must come **immediately** after `claude -p` / `codex
exec`, before any other flags. `--add-dir`, `--allowedTools` (claude) and
`-i/--image` (codex) are variadic flags that otherwise greedily consume
the prompt string as their own value, leaving the CLI with an empty
prompt and a confusing "no prompt provided" error.

## Document conversion before the AI call

Several formats are converted to plain text server-side before staging,
both to make CLI providers (which only get filesystem `Read` access, no
unzip/shell) more reliable and to capture real extracted text for the
search index at effectively no cost:

- **`.odt`** (OpenDocument Text, a zip container): `content.xml` is parsed
  and its text nodes joined.
- **`.xlsx`**: worksheet XML + shared strings parsed directly (no
  spreadsheet library dependency).
- **`.pdf`**: embedded text extracted via `pypdf`; if a PDF has no
  embedded text (a scan), the first pages are rendered to a JPEG via
  PyMuPDF so image-capable providers can still read it.
- **`.html`/`.htm`**: tags stripped, readable text kept (used for mail
  bodies that have no attachment at all, e.g. order-confirmation emails).
- **Photos**: downscaled to a 2000px long side before the AI call (a
  phone photo doesn't need 4000px resolution to read text, and burns
  proportionally more input tokens for no benefit).

Whichever converter produced a `.txt` gets its content indexed as
`full_text` directly (free). For formats with no server-side extraction
(a photo with no separate OCR step), the AI is asked to return the full
transcription itself as part of its structured JSON output — but only
when no text was already inlined into the prompt, to avoid paying to
re-transcribe text we already have for free.

## Data model

See `backend/app/schema.sql`. Key tables: `users` / `sessions` (auth),
`settings` (JSON key/value, used for mail/Telegram/AI-provider config),
`documents` + `documents_fts` (FTS5 virtual table kept in sync via
triggers), `document_events` (audit trail), `ingest_jobs` (every ingest
attempt, success or failure), `document_duplicate_candidates` (fuzzy
duplicate warnings), `saved_views` (the dashboard's "Work views").

FTS5 virtual tables can't have a column added via `ALTER TABLE` — when the
schema needs a new indexed column (e.g. adding `full_text`), the migration
in `db.py` drops and recreates `documents_fts` and its triggers, then runs
the FTS5 `rebuild` command to repopulate it.

## Model recommendations

- **Document extraction** (the core task): Sonnet-tier by default. Runs
  unsupervised against real, often messy documents — accuracy matters
  more than cost here, because a bad extraction means an undiscoverable
  document.
- **"Test connection" in Settings**: a cheap, fast model is enough — it's
  a trivial round-trip check.
- **Duplicate-candidate merging** (if ever escalated to an AI decision
  rather than the current heuristic scoring): a stronger model, since a
  wrong automatic merge is more destructive than a single bad extraction.
