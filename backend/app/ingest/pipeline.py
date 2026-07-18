import hashlib
import mimetypes
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..ai_engine import get_provider
from ..ai_engine.base import ExtractionError
from ..archive.store import place
from ..db import execute

AMOUNT_RE = re.compile(r"([\d]+(?:[.,]\d+)?)\s*([A-Za-z]{2,3})?")


def _parse_amount(amount_raw: str | None) -> tuple[float | None, str | None]:
    if not amount_raw:
        return None, None
    match = AMOUNT_RE.search(amount_raw)
    if not match:
        return None, None
    try:
        value = float(match.group(1).replace(",", "."))
    except ValueError:
        return None, None
    return value, match.group(2)


def process(file_path: Path, source: str, source_detail: str | None = None) -> int:
    """Extract metadata from file_path via the configured AI provider, archive it on
    success, and record it in the documents table. On failure the file is left where
    it was (not moved) so it can be inspected or retried. Returns the new document id.
    """
    original_filename = file_path.name
    mime_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
    file_size = file_path.stat().st_size
    file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()

    # Stage a COPY into an isolated per-job temp dir so the AI provider only ever
    # gets read access to this one document, never the shared inbox/watch-folder
    # it came from (see docs/adr — security tightening vs. the bash prototype).
    with tempfile.TemporaryDirectory(prefix="muninn-job-") as tmp:
        staged = Path(tmp) / original_filename
        shutil.copy2(file_path, staged)

        try:
            provider = get_provider()
            result = provider.extract(staged)
        except ExtractionError as exc:
            cur = execute(
                """INSERT INTO documents
                     (original_filename, stored_path, correspondent, doc_type, source,
                      source_detail, mime_type, file_size, file_hash, status, error_message,
                      created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'failed', ?, ?, ?)""",
                (
                    original_filename, str(file_path), "neznama-firma", "other", source,
                    source_detail, mime_type, file_size, file_hash, str(exc), now, now,
                ),
            )
            return cur.lastrowid

    dest = place(file_path, result["correspondent"], result["doc_type"], result["doc_date"])
    stored_path = str(dest)
    amount_value, amount_currency = _parse_amount(result["amount_raw"])

    cur = execute(
        """INSERT INTO documents
             (original_filename, stored_path, correspondent, doc_type, doc_date, amount_value,
              amount_currency, amount_raw, summary, source, source_detail, ai_provider, ai_model,
              ai_raw_response, mime_type, file_size, file_hash, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed', ?, ?)""",
        (
            original_filename, stored_path, result["correspondent"], result["doc_type"],
            result["doc_date"], amount_value, amount_currency, result["amount_raw"],
            result["summary"], source, source_detail, provider.name, provider.model,
            result["raw_response"], mime_type, file_size, file_hash, now, now,
        ),
    )
    return cur.lastrowid
