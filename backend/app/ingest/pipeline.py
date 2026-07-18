import hashlib
import mimetypes
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from ..ai_engine import get_provider_chain
from ..ai_engine.base import ExtractionError
from ..archive.store import park_duplicate, place
from ..db import execute

AMOUNT_RE = re.compile(r"([\d]+(?:[.,]\d+)?)\s*([A-Za-z]{2,3})?")

# Phone photos are routinely 3000-4000px on the long side, which is far more
# resolution than needed to read text and burns a lot of extra input tokens
# per AI call. Downscaling before the AI call keeps the text legible while
# cutting token/cost per image roughly in half to two-thirds.
MAX_IMAGE_DIMENSION = 2000


def _downscale_image(path: Path, mime_type: str) -> None:
    if not mime_type.startswith("image/"):
        return
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if max(img.size) <= MAX_IMAGE_DIMENSION:
                return
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)
            img.save(path)
    except (UnidentifiedImageError, OSError):
        # Not a format Pillow understands (or a truncated file) -- let the AI
        # provider deal with the original, this isn't fatal to the job.
        pass


def _convert_odt_if_needed(path: Path) -> Path | None:
    """OpenDocument Text (.odt) is a zip container -- the AI only gets the
    read-only `Read` tool (no unzip/bash access, see docs/adr on the
    sandboxing), so handing it the raw binary makes it spin uselessly until
    the subprocess timeout instead of failing fast (seen in production: a
    dropped .odt timed out after 120s twice in a row). Extract the plain
    text server-side so there's something legible to read. Only the staged
    AI-facing copy is affected -- the original .odt is still what gets
    archived."""
    if path.suffix.lower() != ".odt":
        return None
    try:
        with zipfile.ZipFile(path) as zf, zf.open("content.xml") as f:
            tree = ET.parse(f)
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError):
        return None

    text = "\n".join(t.strip() for t in tree.getroot().itertext() if t.strip())
    if not text:
        return None

    text_path = path.with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8")
    return text_path


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


def process(file_path: Path, source: str, source_detail: str | None = None) -> dict:
    """Extract metadata from file_path via the configured AI provider, archive it on
    success, and record it in the documents table. On failure the file is left where
    it was (not moved) so it can be inspected or retried. Returns
    {"document_id": int, "duplicate": bool} -- duplicate is True when a byte-identical
    file was already archived and this call short-circuited without re-running AI
    extraction.
    """
    original_filename = file_path.name
    mime_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
    file_size = file_path.stat().st_size
    file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()

    # Byte-identical file already archived (e.g. the same scan uploaded twice,
    # or a watch-folder re-sync) -- skip the AI call entirely and point back
    # at the existing record instead of creating a duplicate.
    existing = execute(
        "SELECT id FROM documents WHERE file_hash = ? AND status = 'processed' LIMIT 1",
        (file_hash,),
    ).fetchone()
    if existing is not None:
        park_duplicate(file_path)
        return {"document_id": existing["id"], "duplicate": True}

    # Stage a COPY into an isolated per-job temp dir so the AI provider only ever
    # gets read access to this one document, never the shared inbox/watch-folder
    # it came from (see docs/adr — security tightening vs. the bash prototype).
    with tempfile.TemporaryDirectory(prefix="muninn-job-") as tmp:
        staged = Path(tmp) / original_filename
        shutil.copy2(file_path, staged)
        _downscale_image(staged, mime_type)
        staged = _convert_odt_if_needed(staged) or staged

        # In "auto" mode this is claude_cli -> codex_cli -> anthropic_api. If one
        # fails at call time (e.g. usage limits hit, not just "not installed"),
        # fall through to the next rather than failing the whole document.
        chain = get_provider_chain()
        result = None
        provider = None
        last_error: ExtractionError | None = None
        for candidate in chain:
            try:
                result = candidate.extract(staged)
                provider = candidate
                break
            except ExtractionError as exc:
                last_error = exc
                continue

        if result is None:
            error_message = (
                str(last_error) if last_error is not None else
                "Ziadny AI provider nie je k dispozicii - nainstaluj/prihlas sa do "
                "claude alebo codex CLI, alebo nastav Anthropic API kluc v Nastaveniach"
            )
            cur = execute(
                """INSERT INTO documents
                     (original_filename, stored_path, correspondent, doc_type, source,
                      source_detail, mime_type, file_size, file_hash, status, error_message,
                      created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'failed', ?, ?, ?)""",
                (
                    original_filename, str(file_path), "neznama-firma", "other", source,
                    source_detail, mime_type, file_size, file_hash, error_message, now, now,
                ),
            )
            return {"document_id": cur.lastrowid, "duplicate": False}

    dest = place(file_path, result["correspondent"], result["doc_type"], result["doc_date"])
    stored_path = str(dest)
    amount_value, amount_currency = _parse_amount(result["amount_raw"])

    cur = execute(
        """INSERT INTO documents
             (original_filename, stored_path, correspondent, doc_type, doc_date, amount_value,
              amount_currency, amount_raw, summary, source, source_detail, ai_provider, ai_model,
              ai_raw_response, mime_type, file_size, file_hash, cost_usd, input_tokens,
              output_tokens, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed', ?, ?)""",
        (
            original_filename, stored_path, result["correspondent"], result["doc_type"],
            result["doc_date"], amount_value, amount_currency, result["amount_raw"],
            result["summary"], source, source_detail, provider.name, provider.model,
            result["raw_response"], mime_type, file_size, file_hash, result["cost_usd"],
            result["input_tokens"], result["output_tokens"], now, now,
        ),
    )
    return {"document_id": cur.lastrowid, "duplicate": False}
