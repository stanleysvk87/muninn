import csv
import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ...db import execute

router = APIRouter(prefix="/documents", tags=["documents"])

EXPORT_FIELDS = [
    "id", "correspondent", "doc_type", "doc_date", "amount_value",
    "amount_currency", "summary", "original_filename", "stored_path",
]


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


@router.get("")
def list_documents(
    q: str | None = None,
    correspondent: str | None = None,
    doc_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    if q:
        rows = execute(
            """SELECT documents.* FROM documents
               JOIN documents_fts ON documents_fts.rowid = documents.id
               WHERE documents_fts MATCH ?
               ORDER BY documents.created_at DESC LIMIT ? OFFSET ?""",
            (q, limit, offset),
        ).fetchall()
    else:
        clauses, params = [], []
        if correspondent:
            clauses.append("correspondent = ?")
            params.append(correspondent)
        if doc_type:
            clauses.append("doc_type = ?")
            params.append(doc_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = execute(
            f"SELECT * FROM documents {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/export")
def export_documents(format: str = "json", q: str | None = None):
    rows = list_documents(q=q, limit=10000, offset=0)

    if format == "json":
        return rows

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        buffer.seek(0)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=documents.csv"},
        )

    if format == "zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            for row in rows:
                stored_path = Path(row["stored_path"])
                if stored_path.exists():
                    zf.write(stored_path, arcname=f"{row['id']}_{stored_path.name}")
            zf.writestr("manifest.json", json.dumps(rows, indent=2))
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=documents.zip"},
        )

    raise HTTPException(status_code=400, detail="Neznamy format (pouzi json, csv alebo zip)")


@router.get("/{document_id}")
def get_document(document_id: int):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")
    return _row_to_dict(row)


@router.get("/{document_id}/file")
def get_document_file(document_id: int, download: bool = False):
    row = execute(
        "SELECT stored_path, original_filename, mime_type FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")

    path = Path(row["stored_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Subor sa na disku nenasiel (mozno zlyhalo spracovanie)")

    return FileResponse(
        path,
        media_type=row["mime_type"] or "application/octet-stream",
        filename=row["original_filename"] if download else None,
        content_disposition_type="attachment" if download else "inline",
    )


@router.patch("/{document_id}")
def update_document(document_id: int, payload: dict):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")

    allowed = {"correspondent", "doc_type", "doc_date", "amount_value", "amount_currency", "summary"}
    fields = {k: v for k, v in payload.items() if k in allowed}
    if fields:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        execute(
            f"UPDATE documents SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            (*fields.values(), document_id),
        )
    return get_document(document_id)


@router.delete("/{document_id}")
def delete_document(document_id: int):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")
    execute("DELETE FROM documents WHERE id = ?", (document_id,))
    return {"ok": True}
