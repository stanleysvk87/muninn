import asyncio
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile
from PIL import Image
from pypdf import PdfReader, PdfWriter

from ...config import settings
from ...errors import api_error
from ...ingest import pipeline

router = APIRouter(prefix="/upload", tags=["upload"])

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
# Deliberately no .svg: an SVG is a script-capable document, not a picture,
# and there is no reason to accept one as an archived "scan". Everything
# here is either something the ingest pipeline has a text converter for
# (see ingest/pipeline.py) or something an AI provider can read directly.
DOCUMENT_SUFFIXES = {
    ".pdf", ".txt", ".md", ".csv", ".html", ".htm",
    ".odt", ".ods", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf", ".eml",
}
ALLOWED_UPLOAD_SUFFIXES = IMAGE_SUFFIXES | DOCUMENT_SUFFIXES
_CHUNK_BYTES = 1024 * 1024


class _UploadTooLarge(Exception):
    pass


def _max_upload_bytes() -> int:
    return settings.max_upload_mb * 1024 * 1024


def _check_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise api_error(422, "upload_unsupported_format", suffix=suffix or "?")
    return suffix


def _stage_upload(file: UploadFile, dest: Path) -> None:
    """Copy an upload to disk with a hard size ceiling. shutil.copyfileobj
    used to stream it unbounded, so one authenticated request (or an XSS
    riding the session) could fill the boot volume -- tempfile writes to
    /tmp, not to the archive volume."""
    limit = _max_upload_bytes()
    total = 0
    with dest.open("wb") as out:
        while True:
            chunk = file.file.read(_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise _UploadTooLarge
            out.write(chunk)


@router.post("")
async def upload(file: UploadFile):
    if not file.filename:
        raise api_error(422, "invalid_filename")
    _check_suffix(file.filename)

    tmp_dir = Path(tempfile.mkdtemp(prefix="muninn-upload-"))
    try:
        dest = tmp_dir / Path(file.filename).name
        try:
            await asyncio.to_thread(_stage_upload, file, dest)
        except _UploadTooLarge:
            raise api_error(413, "upload_too_large", limit_mb=settings.max_upload_mb) from None

        # pipeline.process() shells out to the claude/codex CLIs with a
        # 120s timeout per provider (up to ~6 minutes across the chain).
        # Called directly from an async def route it ran ON the event loop
        # and froze every other request, the mail poller and the retry queue
        # for its whole duration -- hand it to a worker thread instead.
        return await asyncio.to_thread(pipeline.process, dest, "upload")
    finally:
        # On success pipeline.process moved dest into the archive; on failure
        # it parked it under archive/_failed. Either way the temp dir must go,
        # including when the request blew up in between (it used to leak the
        # sensitive document into /tmp permanently on any exception).
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _combine_to_pdf(paths: list[Path], dest: Path) -> None:
    """Merge photos/PDFs (in the given order) into a single multi-page PDF --
    e.g. a 10-page contract photographed one page at a time should become one
    archived document, not ten. Each image page is rendered to its own
    one-page PDF via Pillow, then all pages are combined with pypdf (already
    a dependency for PDF text extraction elsewhere in the pipeline)."""
    writer = PdfWriter()
    for path in paths:
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
        else:
            page_pdf = path.with_suffix(path.suffix + ".page.pdf")
            with Image.open(path) as img:
                img.convert("RGB").save(page_pdf, "PDF")
            reader = PdfReader(str(page_pdf))
        for page in reader.pages:
            writer.add_page(page)

    with dest.open("wb") as f:
        writer.write(f)


@router.post("/combine")
async def upload_combine(files: list[UploadFile]):
    if len(files) < 2:
        raise api_error(422, "merge_needs_two_files")

    tmp_dir = Path(tempfile.mkdtemp(prefix="muninn-upload-combine-"))
    try:
        staged_paths = []
        for index, file in enumerate(files):
            if not file.filename:
                raise api_error(422, "invalid_filename")
            suffix = Path(file.filename).suffix.lower()
            if suffix != ".pdf" and suffix not in IMAGE_SUFFIXES:
                raise api_error(422, "merge_unsupported_format", suffix=suffix or "?")
            path = tmp_dir / f"{index:03d}_{Path(file.filename).name}"
            try:
                await asyncio.to_thread(_stage_upload, file, path)
            except _UploadTooLarge:
                raise api_error(413, "upload_too_large", limit_mb=settings.max_upload_mb) from None
            staged_paths.append(path)

        combined_path = tmp_dir / f"zlucene_{len(files)}_stran.pdf"
        try:
            await asyncio.to_thread(_combine_to_pdf, staged_paths, combined_path)
        except Exception as exc:
            raise api_error(422, "merge_failed", error=str(exc)) from exc

        # Same reason as the single-file route: never run the AI subprocess
        # chain on the event loop.
        return await asyncio.to_thread(pipeline.process, combined_path, "upload")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
