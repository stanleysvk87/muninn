# Testing

```
cd backend
python3 -m venv venv && venv/bin/pip install -r requirements.txt -r requirements-dev.txt
venv/bin/pytest
```

Tests run against a real FastAPI app instance and a real (temporary,
session-scoped) SQLite database created fresh under a temp directory —
not against production data, and not against `docker compose`. AI
providers are never actually invoked: `pipeline.get_provider_chain()` is
monkeypatched per test to return small `FakeProvider` test doubles that
either succeed with a controlled result or raise a controlled exception,
so the suite runs fully offline and deterministically, with no CLI/API
dependency and no cost.

## What's covered

- **Auth** (`test_auth.py`): bootstrap requires explicit consent (the
  GDPR-style gate), wrong password rejected, unauthenticated requests
  rejected, logout actually clears the session.
- **Ingestion pipeline** (`test_ingest.py`): a successful extraction
  produces a `processed` document; a byte-identical re-upload is detected
  as a duplicate and never triggers a second AI call; if every provider
  fails with a `ProviderUnavailableError` (rate limit/auth/timeout/no
  provider configured) the document lands as `pending`, not `failed`; a
  genuine content-level failure (`ExtractionError`) still lands as
  `failed`, including when mixed with an unavailable provider earlier in
  the chain; retrying a `pending` document via `reprocess_document()`
  updates the same row in place instead of inserting a duplicate.
- **Full-text search** (`test_search.py`): a term that only appears in the
  document body (not the correspondent/type/summary) is still found, with
  a highlighted snippet showing the match.
- **Documents API** (`test_documents_api.py`): deleting a document removes
  the archived file from disk, not just the database row (the GDPR
  right-of-erasure fix); state-changing requests are rejected without a
  valid CSRF token; expiry dismiss/restore round-trips correctly and
  affects the "expiring" list; review-status transitions are validated
  against the allowed set.

## What isn't covered yet

- The frontend (React/Vite) has no automated test suite — verification so
  far has been manual/Playwright-assisted during development, not CI.
- Real calls to `claude`/`codex` CLI or the Anthropic API are never
  exercised by this suite by design (see above) — they were verified
  manually against live providers during development instead.
- The mail poller, watch-folder observer, Telegram notifier, and
  expiry/recurrence background loops are not covered by automated tests.
