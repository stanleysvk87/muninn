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
    # On success pipeline.process moved dest into the archive. On failure it
    # parks dest under archive/_failed before this temp-dir cleanup runs.
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return result
