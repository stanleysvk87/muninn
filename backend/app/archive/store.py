import re
import shutil
from datetime import date
from pathlib import Path

from ..config import settings


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "neznama-firma"


def place(file_path: Path, correspondent: str, doc_type: str, doc_date: str | None) -> Path:
    """Move file_path into archive_dir/<correspondent>/, collision-safe. Returns the new path."""
    dest_dir = settings.archive_dir / _slugify(correspondent)
    dest_dir.mkdir(parents=True, exist_ok=True)

    date_part = doc_date or date.today().isoformat()
    base_name = f"{date_part}_{_slugify(doc_type)}_{file_path.stem}"
    dest = dest_dir / f"{base_name}{file_path.suffix}"

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
    dest = dest_dir / file_path.name

    i = 1
    while dest.exists():
        dest = dest_dir / f"{file_path.stem}-{i}{file_path.suffix}"
        i += 1

    shutil.move(str(file_path), str(dest))
    return dest
