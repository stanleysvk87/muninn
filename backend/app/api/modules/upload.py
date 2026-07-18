import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from ...ingest import pipeline

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("")
async def upload(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=422, detail="Chyba nazov suboru")

    tmp_dir = Path(tempfile.mkdtemp(prefix="muninn-upload-"))
    dest = tmp_dir / file.filename
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    result = pipeline.process(dest, source="upload")
    # On success pipeline.process already moved dest into the archive; on
    # failure it's left here and this cleanup discards it (upload source
    # files aren't worth preserving on disk the way watch-folder ones are —
    # the user still has the original on their device to re-upload).
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return result
