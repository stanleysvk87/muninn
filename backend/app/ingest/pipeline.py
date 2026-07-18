import hashlib
import json
import logging
import mimetypes
import re
import shutil
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple

from PIL import Image, ImageOps, UnidentifiedImageError

from ..ai_engine import get_provider_chain
from ..ai_engine.base import AIProvider, ExtractionError, ProviderUnavailableError
from ..audit import add_document_event, finish_ingest_job, start_ingest_job
from ..archive.store import park_duplicate, park_failed, place
from ..db import execute
from ..duplicates import record_duplicate_candidates

logger = logging.getLogger("muninn.ingest.pipeline")

AMOUNT_RE = re.compile(r"([\d]+(?:[.,]\d+)?)\s*([A-Za-z]{2,3})?")
EXTENSION_MIME_TYPES = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
}
BAD_RESULT_PHRASES = (
    "nepodarilo sa precitat",
    "nepodarilo precitat",
    "neviem precitat",
    "neviem otvorit",
    "nemam pristup",
    "nema pristup",
    "sandbox",
    "subor sa nepodarilo",
    "dokument sa nepodarilo",
    "could not read",
    "cannot read",
    "cannot access",
    "failed before opening",
    "local sandbox",
)

# Phone photos are routinely 3000-4000px on the long side, which is far more
# resolution than needed to read text and burns a lot of extra input tokens
# per AI call. Downscaling before the AI call keeps the text legible while
# cutting token/cost per image roughly in half to two-thirds.
MAX_IMAGE_DIMENSION = 2000


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "head"}:
            self._skip_depth += 1
        elif tag in {"br", "p", "div", "tr", "li", "table"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "head"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"p", "div", "tr", "li", "table"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.parts.append(text)


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


def _convert_xlsx_if_needed(path: Path) -> Path | None:
    """Extract readable worksheet text from .xlsx files. XLSX is a ZIP full of
    XML parts; giving the binary container to CLI providers makes them infer
    from the filename instead of reading cells.
    """
    if path.suffix.lower() != ".xlsx":
        return None

    try:
        with zipfile.ZipFile(path) as zf:
            shared_strings = _read_xlsx_shared_strings(zf)
            sheet_names = sorted(
                name for name in zf.namelist()
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            )
            sheets = []
            for sheet_index, sheet_name in enumerate(sheet_names, start=1):
                try:
                    rows = _read_xlsx_sheet(zf, sheet_name, shared_strings)
                except ET.ParseError:
                    continue
                if rows:
                    sheets.append(f"--- harok {sheet_index} ---\n" + "\n".join(rows))
    except (zipfile.BadZipFile, KeyError, OSError):
        return None

    text = "\n\n".join(sheets).strip()
    if not text:
        return None

    text_path = path.with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8")
    return text_path


def _read_xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.itertext()).strip() for node in root]


def _read_xlsx_sheet(
    zf: zipfile.ZipFile,
    sheet_name: str,
    shared_strings: list[str],
) -> list[str]:
    root = ET.fromstring(zf.read(sheet_name))
    rows: list[str] = []
    for row in root.iter():
        if not row.tag.endswith("row"):
            continue
        values = []
        for cell in row:
            if not cell.tag.endswith("c"):
                continue
            values.append(_read_xlsx_cell(cell, shared_strings))
        while values and not values[-1]:
            values.pop()
        if any(values):
            rows.append("\t".join(values))
    return rows


def _read_xlsx_cell(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return " ".join(t.strip() for t in cell.itertext() if t.strip())

    value_node = next((child for child in cell if child.tag.endswith("v")), None)
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text.strip()
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value
    return value


def _convert_html_if_needed(path: Path) -> Path | None:
    if path.suffix.lower() not in {".html", ".htm"}:
        return None
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    parser = _HTMLTextExtractor()
    parser.feed(html)
    text = "\n".join(part for part in parser.parts if part.strip())
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return None

    text_path = path.with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8")
    return text_path


def _convert_pdf_if_needed(path: Path) -> Path | None:
    """For Codex fallback, a PDF path inside a read-only sandbox is much less
    reliable than plain text. Extract embedded PDF text server-side when it is
    available and let the AI read a .txt copy. Scanned PDFs without embedded
    text still fall back to the original file for providers that can handle it.
    """
    if path.suffix.lower() != ".pdf":
        return None
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("PDF text extraction unavailable: pypdf is not installed")
        return _render_pdf_preview_if_needed(path)

    try:
        reader = PdfReader(str(path))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append(f"--- strana {index} ---\n{text}")
    except Exception as exc:
        logger.warning("PDF text extraction failed for %s: %s", path.name, exc)
        return _render_pdf_preview_if_needed(path)

    text = "\n\n".join(pages).strip()
    if not text:
        return _render_pdf_preview_if_needed(path)

    text_path = path.with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8")
    return text_path


def _render_pdf_preview_if_needed(path: Path, max_pages: int = 2) -> Path | None:
    """Fallback for scanned/image PDFs: render the first pages into one JPEG so
    image-capable providers (especially codex with -i) can inspect it. This is
    not full OCR, but it is enough for common one-page invoices and reminders.
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PDF image rendering unavailable: PyMuPDF is not installed")
        return None

    try:
        doc = fitz.open(str(path))
        images = []
        for page_index in range(min(max_pages, len(doc))):
            page = doc[page_index]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(img)
    except Exception as exc:
        logger.warning("PDF image rendering failed for %s: %s", path.name, exc)
        return None
    finally:
        try:
            doc.close()
        except Exception:
            pass

    if not images:
        return None

    width = max(img.width for img in images)
    height = sum(img.height for img in images)
    combined = Image.new("RGB", (width, height), "white")
    y = 0
    for img in images:
        combined.paste(img, ((width - img.width) // 2, y))
        y += img.height

    preview_path = path.with_suffix(".jpg")
    combined.thumbnail((2000, 4000), Image.LANCZOS)
    combined.save(preview_path, quality=88, optimize=True)
    return preview_path


def _normalize_for_detection(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return ascii_text.lower()


def _validate_result(result: dict) -> None:
    combined = "\n".join(
        str(result.get(key) or "")
        for key in ("correspondent", "doc_type", "summary", "raw_response")
    )
    normalized = _normalize_for_detection(combined)
    if any(phrase in normalized for phrase in BAD_RESULT_PHRASES):
        raise ExtractionError("AI provider vratil technicke zlyhanie namiesto citatelnej extrakcie")


def _strip_nul(value):
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {key: _strip_nul(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_strip_nul(item) for item in value]
    return value


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


class ChainResult(NamedTuple):
    result: dict | None
    provider: AIProvider | None
    provider_name: str | None
    provider_model: str | None
    raw_response: str | None
    full_text: str | None
    # True only if every provider actually attempted failed with
    # ProviderUnavailableError (rate limit/auth/timeout/missing binary) --
    # i.e. nothing about this specific document is the problem, it's just
    # that no provider could be reached. False if at least one provider
    # genuinely tried and rejected the content, or the chain is configured
    # but hasn't been attempted at all for some other reason.
    all_unavailable: bool
    error: ExtractionError | None


def _extract_via_chain(file_path: Path, mime_type: str) -> ChainResult:
    """Stage file_path into an isolated per-job temp dir (the AI provider
    only ever gets read access to this one document, never the shared
    inbox/watch-folder it came from -- see docs/adr, security tightening vs.
    the bash prototype), convert it to plain text when a converter applies,
    and try each provider in the configured chain until one succeeds."""
    with tempfile.TemporaryDirectory(prefix="muninn-job-") as tmp:
        staged = Path(tmp) / file_path.name
        shutil.copy2(file_path, staged)
        _downscale_image(staged, mime_type)
        staged = (
            _convert_odt_if_needed(staged)
            or _convert_xlsx_if_needed(staged)
            or _convert_pdf_if_needed(staged)
            or _convert_html_if_needed(staged)
            or staged
        )
        # If a conversion above produced a .txt, that's real extracted text
        # (free, already computed) -- prefer it over asking the AI to
        # transcribe it again in its JSON output. Only images/other formats
        # without a converter fall back to the AI's own full_text field.
        converted_text = (
            staged.read_text(encoding="utf-8", errors="replace")
            if staged.suffix.lower() == ".txt"
            else None
        )

        # In "auto" mode this is claude_cli -> codex_cli -> anthropic_api. If one
        # fails at call time (e.g. usage limits hit, not just "not installed"),
        # fall through to the next rather than failing the whole document.
        chain = get_provider_chain()
        result = None
        provider = None
        last_error: ExtractionError | None = None
        last_provider_name: str | None = None
        last_provider_model: str | None = None
        last_raw_response: str | None = None
        all_unavailable = True
        for candidate in chain:
            candidate_result = None
            last_provider_name = candidate.name
            last_provider_model = candidate.model
            try:
                candidate_result = _strip_nul(candidate.extract(staged))
                last_raw_response = candidate_result.get("raw_response")
                _validate_result(candidate_result)
                result = candidate_result
                provider = candidate
                break
            except ExtractionError as exc:
                if candidate_result is not None:
                    last_raw_response = candidate_result.get("raw_response")
                if not isinstance(exc, ProviderUnavailableError):
                    all_unavailable = False
                last_error = exc
                logger.warning(
                    "AI provider %s failed for %s: %s",
                    candidate.name,
                    file_path.name,
                    exc,
                )
                continue

        full_text = converted_text or (result.get("full_text") if result else None)
        return ChainResult(
            result=result,
            provider=provider,
            provider_name=last_provider_name,
            provider_model=last_provider_model,
            raw_response=last_raw_response,
            full_text=full_text,
            all_unavailable=all_unavailable,
            error=last_error,
        )


def process(file_path: Path, source: str, source_detail: str | None = None) -> dict:
    """Extract metadata from file_path via the configured AI provider, archive it on
    success, and record it in the documents table. On failure the file is parked
    under archive/_failed so temp uploads/mail parts remain inspectable. Returns
    {"document_id": int, "duplicate": bool, "status": str} -- duplicate is True when
    a byte-identical file was already archived and this call short-circuited without
    re-running AI extraction.
    """
    original_filename = file_path.name
    mime_type = (
        EXTENSION_MIME_TYPES.get(file_path.suffix.lower())
        or mimetypes.guess_type(original_filename)[0]
        or "application/octet-stream"
    )
    file_size = file_path.stat().st_size
    file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    job_id = start_ingest_job(source, source_detail, original_filename)

    # Byte-identical file already archived (e.g. the same scan uploaded twice,
    # or a watch-folder re-sync) -- skip the AI call entirely and point back
    # at the existing record instead of creating a duplicate.
    existing = execute(
        "SELECT id FROM documents WHERE file_hash = ? AND status = 'processed' LIMIT 1",
        (file_hash,),
    ).fetchone()
    if existing is not None:
        park_duplicate(file_path)
        finish_ingest_job(
            job_id,
            status="duplicate",
            document_id=existing["id"],
            duplicate=True,
        )
        add_document_event(
            existing["id"],
            "duplicate_exact",
            f"Preskoceny byte-identicky duplicitny subor {original_filename}",
            metadata={"source": source, "source_detail": source_detail},
        )
        return {"document_id": existing["id"], "duplicate": True, "status": "processed"}

    chain_result = _extract_via_chain(file_path, mime_type)

    if chain_result.result is None:
        # If no provider could even be reached (rate limit/auth/timeout/
        # missing binary, across the whole chain) this document's content
        # was never actually the problem -- queue it for automatic retry
        # (see queue_retry.py) instead of marking it a permanent failure.
        status = "pending" if chain_result.all_unavailable else "failed"
        error_message = (
            str(chain_result.error) if chain_result.error is not None else
            "Ziadny AI provider nie je k dispozicii - nainstaluj/prihlas sa do "
            "claude alebo codex CLI, alebo nastav Anthropic API kluc v Nastaveniach"
        )
        failed_path = str(file_path)
        if file_path.exists():
            try:
                failed_path = str(park_failed(file_path, source))
            except OSError:
                logger.exception("Nepodarilo sa odlozit zlyhany subor %s", file_path)
        cur = execute(
            """INSERT INTO documents
                 (original_filename, stored_path, correspondent, doc_type, source,
                  source_detail, ai_provider, ai_model, ai_raw_response, mime_type,
                  file_size, file_hash, status, error_message,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                original_filename, failed_path, "neznama-firma", "other", source,
                source_detail, chain_result.provider_name, chain_result.provider_model,
                chain_result.raw_response, mime_type, file_size, file_hash, status,
                error_message, now, now,
            ),
        )
        document_id = cur.lastrowid
        finish_ingest_job(
            job_id,
            status=status,
            document_id=document_id,
            ai_provider=chain_result.provider_name,
            error_message=error_message,
        )
        add_document_event(
            document_id,
            "ingest_pending" if status == "pending" else "ingest_failed",
            error_message,
            metadata={"source": source, "source_detail": source_detail},
        )
        return {
            "document_id": document_id,
            "duplicate": False,
            "status": status,
            "error_message": error_message,
        }

    result = chain_result.result
    dest = place(file_path, result["correspondent"], result["doc_type"], result["doc_date"])
    stored_path = str(dest)
    amount_value, amount_currency = _parse_amount(result["amount_raw"])
    full_text = chain_result.full_text

    cur = execute(
        """INSERT INTO documents
             (original_filename, stored_path, correspondent, doc_type, doc_date, expiry_date,
              amount_value, amount_currency, amount_raw, summary, source, source_detail,
              ai_provider, ai_model, ai_raw_response, mime_type, file_size, file_hash, cost_usd,
              input_tokens, output_tokens, evidence_json, full_text, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed', ?, ?)""",
        (
            original_filename, stored_path, result["correspondent"], result["doc_type"],
            result["doc_date"], result["expiry_date"], amount_value, amount_currency,
            result["amount_raw"], result["summary"], source, source_detail, chain_result.provider.name,
            chain_result.provider.model, result["raw_response"], mime_type, file_size, file_hash,
            result["cost_usd"], result["input_tokens"], result["output_tokens"],
            json.dumps(result.get("evidence") or [], ensure_ascii=False), full_text, now, now,
        ),
    )
    document_id = cur.lastrowid
    finish_ingest_job(
        job_id,
        status="processed",
        document_id=document_id,
        ai_provider=chain_result.provider.name,
    )
    add_document_event(
        document_id,
        "ingested",
        f"Dokument spracovany cez {chain_result.provider.name}",
        metadata={
            "source": source,
            "source_detail": source_detail,
            "model": chain_result.provider.model,
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
        },
    )
    record_duplicate_candidates(document_id)
    return {"document_id": document_id, "duplicate": False, "status": "processed"}


def reprocess_document(document_id: int) -> dict:
    """Re-run AI extraction for an existing failed/pending document, updating
    its row in place. Unlike process() (which always inserts a new row --
    appropriate for a first-time ingest), a retry must not accumulate a new
    row every time it's attempted: the automatic pending-queue retry loop
    (queue_retry.py) may call this many times for the same document before a
    provider comes back, and the manual "Retry" button in Settings would
    otherwise leave the original failed row behind as orphaned history."""
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        return {"document_id": document_id, "status": None, "skipped": True}
    if row["status"] not in ("failed", "pending"):
        return {"document_id": document_id, "status": row["status"], "skipped": True}

    path = Path(row["stored_path"])
    if not path.is_file():
        return {
            "document_id": document_id,
            "status": row["status"],
            "skipped": True,
            "error": "zdrojovy subor sa na disku nenasiel",
        }

    now = datetime.now(timezone.utc).isoformat()
    mime_type = (
        row["mime_type"]
        or EXTENSION_MIME_TYPES.get(path.suffix.lower())
        or mimetypes.guess_type(row["original_filename"])[0]
        or "application/octet-stream"
    )

    chain_result = _extract_via_chain(path, mime_type)

    if chain_result.result is None:
        new_status = "pending" if chain_result.all_unavailable else "failed"
        error_message = (
            str(chain_result.error) if chain_result.error is not None else row["error_message"]
        )
        execute(
            """UPDATE documents SET status = ?, error_message = ?, ai_provider = ?,
                 ai_model = ?, updated_at = ? WHERE id = ?""",
            (new_status, error_message, chain_result.provider_name, chain_result.provider_model, now, document_id),
        )
        return {
            "document_id": document_id,
            "duplicate": False,
            "status": new_status,
            "error_message": error_message,
        }

    result = chain_result.result
    dest = place(path, result["correspondent"], result["doc_type"], result["doc_date"])
    amount_value, amount_currency = _parse_amount(result["amount_raw"])

    execute(
        """UPDATE documents SET
             stored_path = ?, correspondent = ?, doc_type = ?, doc_date = ?, expiry_date = ?,
             amount_value = ?, amount_currency = ?, amount_raw = ?, summary = ?,
             ai_provider = ?, ai_model = ?, ai_raw_response = ?, cost_usd = ?, input_tokens = ?,
             output_tokens = ?, evidence_json = ?, full_text = ?, status = 'processed',
             error_message = NULL, updated_at = ?
           WHERE id = ?""",
        (
            str(dest), result["correspondent"], result["doc_type"], result["doc_date"],
            result["expiry_date"], amount_value, amount_currency, result["amount_raw"],
            result["summary"], chain_result.provider.name, chain_result.provider.model,
            result["raw_response"], result["cost_usd"], result["input_tokens"],
            result["output_tokens"], json.dumps(result.get("evidence") or [], ensure_ascii=False),
            chain_result.full_text, now, document_id,
        ),
    )
    record_duplicate_candidates(document_id)
    return {"document_id": document_id, "duplicate": False, "status": "processed"}
