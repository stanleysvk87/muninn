import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from PIL import Image
from pypdf import PdfReader, PdfWriter

from ...ingest import pipeline

router = APIRouter(prefix="/upload", tags=["upload"])

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


@router.post("")
async def upload(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=422, detail="Chyba nazov suboru")

    tmp_dir = Path(tempfile.mkdtemp(prefix="muninn-upload-"))
    dest = tmp_dir / file.filename
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    result = pipeline.process(dest, source="upload")
    # On success pipeline.process moved dest into the archive. On failure it
    # parks dest under archive/_failed before this temp-dir cleanup runs.
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return result


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
        raise HTTPException(status_code=422, detail="Zlucenie potrebuje aspon 2 subory")

    tmp_dir = Path(tempfile.mkdtemp(prefix="muninn-upload-combine-"))
    try:
        staged_paths = []
        for index, file in enumerate(files):
            if not file.filename:
                raise HTTPException(status_code=422, detail="Chyba nazov suboru")
            suffix = Path(file.filename).suffix.lower()
            if suffix != ".pdf" and suffix not in IMAGE_SUFFIXES:
                raise HTTPException(
                    status_code=422,
                    detail=f"Zlucenie podporuje len obrazky a PDF, nie {suffix or 'neznamy format'}",
                )
            path = tmp_dir / f"{index:03d}_{file.filename}"
            with path.open("wb") as out:
                shutil.copyfileobj(file.file, out)
            staged_paths.append(path)

        combined_path = tmp_dir / f"zlucene_{len(files)}_stran.pdf"
        try:
            _combine_to_pdf(staged_paths, combined_path)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Zlucenie suborov zlyhalo: {exc}") from exc

        return pipeline.process(combined_path, source="upload")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
