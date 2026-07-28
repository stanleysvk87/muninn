import re
import shutil
from datetime import date
from pathlib import Path

from ..config import settings


ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_SLUG_LENGTH = 60


def _slugify(text: str, fallback: str = "neznama-firma") -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", str(text)).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:MAX_SLUG_LENGTH].strip("-") or fallback


def _slugify_date(doc_date: str | None) -> str:
    """doc_date comes straight out of the AI's JSON extraction, i.e. out of
    content an attacker can influence (a prompt-injected document can make
    the model return whatever it likes here; only the anthropic_api provider
    even has a schema, and that schema has no pattern). It used to be
    interpolated into the archive filename raw, so a date like
    '../../frontend/dist/x' wrote the document outside archive_dir --
    reproducibly, into the directory the SPA fallback serves from, which
    chained straight into the stored-XSS finding. Slugify it exactly like
    correspondent/doc_type already were: a well-formed ISO date is kept
    as-is, anything else is reduced to a single safe path component instead
    of being silently thrown away (a model returning '2026-01' or
    'january 2026' still carries information)."""
    candidate = (doc_date or "").strip()
    if ISO_DATE_RE.match(candidate):
        return candidate
    if candidate:
        return _slugify(candidate, fallback=date.today().isoformat())
    return date.today().isoformat()


def _safe_stem(file_path: Path) -> str:
    """The stem comes from a user/mail-supplied filename. Path().name already
    strips directories at the ingest boundary, but keep this defensive: no
    separators, no leading dots, bounded length."""
    stem = file_path.stem.replace("/", "-").replace("\\", "-").replace("\x00", "")
    stem = stem.strip().strip(".")
    return stem[:MAX_SLUG_LENGTH] or "dokument"


def _assert_inside_archive(dest: Path) -> Path:
    """Final backstop for every write into the archive: no matter what the
    components above produced, the resolved destination must stay under
    archive_dir."""
    archive_root = settings.archive_dir.resolve()
    resolved = dest.resolve()
    if not resolved.is_relative_to(archive_root):
        raise ValueError(f"cielova cesta je mimo archivu: {resolved}")
    return dest


def place(file_path: Path, correspondent: str, doc_type: str, doc_date: str | None) -> Path:
    """Move file_path into archive_dir/<correspondent>/, collision-safe. Returns the new path."""
    dest_dir = settings.archive_dir / _slugify(correspondent)
    _assert_inside_archive(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    date_part = _slugify_date(doc_date)
    base_name = f"{date_part}_{_slugify(doc_type, fallback='other')}_{_safe_stem(file_path)}"
    dest = dest_dir / f"{base_name}{file_path.suffix}"
    _assert_inside_archive(dest)

    i = 1
    while dest.exists():
        dest = dest_dir / f"{base_name}-{i}{file_path.suffix}"
        i += 1

    # shutil.move (not Path.rename) — the source may be on a different
    # filesystem than the archive dir (e.g. /tmp upload staging vs. a bind-
    # mounted archive volume), where a plain rename() raises EXDEV.
    shutil.move(str(file_path), str(dest))
    return dest


def park_duplicate(file_path: Path) -> Path:
    """A byte-identical re-upload short-circuits before the AI call (see
    ingest/pipeline.py) and never gets a place() call -- move it out of
    wherever it came from anyway, so a watch folder that keeps receiving the
    same file (e.g. a re-synced scan) doesn't pile up with leftovers."""
    dest_dir = settings.archive_dir / "_duplicates"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(file_path)
    dest = dest_dir / f"{stem}{file_path.suffix}"

    i = 1
    while dest.exists():
        dest = dest_dir / f"{stem}-{i}{file_path.suffix}"
        i += 1
    _assert_inside_archive(dest)

    shutil.move(str(file_path), str(dest))
    return dest


def park_failed(file_path: Path, source: str) -> Path:
    """Move a failed source document into the archive so uploads/mail temp files
    stay available for inspection and manual retry after their temp dirs vanish.
    """
    dest_dir = settings.archive_dir / "_failed" / _slugify(source, fallback="unknown")
    _assert_inside_archive(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{date.today().isoformat()}_{_safe_stem(file_path)}"
    dest = dest_dir / f"{base_name}{file_path.suffix}"

    i = 1
    while dest.exists():
        dest = dest_dir / f"{base_name}-{i}{file_path.suffix}"
        i += 1
    _assert_inside_archive(dest)

    shutil.move(str(file_path), str(dest))
    return dest
