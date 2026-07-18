# ADR 0003: A "pending" status for AI provider outages, separate from "failed"

## Context

If every configured AI provider failed to extract a document (rate limit
hit, auth issue, no network — anything short of the model actually
rejecting the content), the original implementation marked the document
`failed`, identical in status to a document whose content was genuinely
unreadable. That conflated two very different situations:

- "This document is broken/unreadable, a human needs to look at it" —
  retrying won't help.
- "Nothing is wrong with this document, there was just nobody to ask
  right now" — retrying automatically, later, is exactly the right fix.

Mixing them meant a temporary provider outage (a rate limit, a brief
network blip) permanently cluttered the "failed" list with documents that
would have processed fine on the next attempt, and required a manual
retry click for something that should have resolved itself.

## Decision

Introduce `ProviderUnavailableError` (a subclass of the existing
`ExtractionError`), raised specifically for availability-class failures —
detected via each provider's own signal (`claude_cli`'s API error
envelope status code, `codex_cli`'s stderr patterns, `anthropic_api`'s
`APIStatusError`/`APIConnectionError`). A document only lands in the new
`pending` status if **every** provider actually attempted failed with
`ProviderUnavailableError` (or none were configured at all) — any genuine
content-level rejection still produces `failed`.

A background loop (`queue_retry.py`) retries `pending` documents every 10
minutes, updating the same database row in place rather than accumulating
a new row per attempt (unlike first-time ingest). Once a provider comes
back, the document quietly finishes processing with no user action
required; if it now fails for a real content reason, it correctly moves
to `failed` instead of retrying forever.

## Consequences

- The "failed" list and its dashboard count are now trustworthy signals
  of documents that actually need a human decision, not diluted by
  transient outages.
- Slightly more classification logic is required per provider (mapping
  raw errors to the right exception type) instead of a single catch-all
  `except Exception`.
- The manual "Retry" button and the automatic queue share the same
  `reprocess_document()` code path, so there's exactly one way a
  failed/pending document gets re-attempted, not two slightly different
  ones.
