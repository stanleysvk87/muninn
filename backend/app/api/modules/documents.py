import csv
import io
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ...audit import add_document_event
from ...db import execute
from ...expiry_notifier import RECURRENCE_MONTHS, _add_months

router = APIRouter(prefix="/documents", tags=["documents"])

EXPORT_FIELDS = [
    "id", "correspondent", "doc_type", "doc_date", "amount_value",
    "amount_currency", "summary", "summary_sk", "summary_en", "original_filename", "stored_path",
]

DOWNLOAD_ONLY_MIME_TYPES = {
    "application/octet-stream",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
EXTENSION_MIME_TYPES = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
}


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


def _document_payload(row) -> dict:
    data = _row_to_dict(row)
    evidence_json = data.pop("evidence_json", None)
    try:
        data["evidence"] = json.loads(evidence_json) if evidence_json else []
    except json.JSONDecodeError:
        data["evidence"] = []
    data["duplicate_warning_count"] = execute(
        """SELECT COUNT(*) AS count FROM document_duplicate_candidates
           WHERE status = 'open' AND (document_id = ? OR candidate_id = ?)""",
        (data["id"], data["id"]),
    ).fetchone()["count"]
    return data


def _download_mime_type(path: Path, stored_mime_type: str | None) -> str:
    return EXTENSION_MIME_TYPES.get(path.suffix.lower()) or stored_mime_type or "application/octet-stream"


def _delete_stored_file(stored_path: str) -> None:
    path = Path(stored_path)
    if not path.exists():
        return
    if not path.is_file():
        raise HTTPException(status_code=409, detail="Ulozena cesta nie je subor; odmietam ju zmazat automaticky")
    try:
        path.unlink()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Nepodarilo sa zmazat subor z disku: {exc}") from exc


def _saved_view_clauses(saved_view: str | None) -> tuple[list[str], list]:
    if not saved_view:
        return [], []
    view = execute("SELECT query_json FROM saved_views WHERE key = ?", (saved_view,)).fetchone()
    if view is None:
        raise HTTPException(status_code=404, detail="Saved view nenajdeny")
    try:
        query = json.loads(view["query_json"])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Saved view ma neplatnu konfiguraciu") from exc

    clauses: list[str] = []
    params: list = []
    if query.get("review_status"):
        clauses.append("review_status = ?")
        params.append(query["review_status"])
    if query.get("status"):
        clauses.append("status = ?")
        params.append(query["status"])
    if query.get("expiring"):
        horizon = (date.today() + timedelta(days=60)).isoformat()
        clauses.append(
            "status = 'processed' AND expiry_date IS NOT NULL "
            "AND expiry_dismissed_at IS NULL AND expiry_date <= ?"
        )
        params.append(horizon)
    if query.get("duplicates"):
        clauses.append(
            "EXISTS (SELECT 1 FROM document_duplicate_candidates dc "
            "WHERE dc.status = 'open' AND (dc.document_id = documents.id OR dc.candidate_id = documents.id))"
        )
    return clauses, params


def _list_documents_query(
    *,
    q: str | None = None,
    correspondent: str | None = None,
    doc_type: str | None = None,
    review_status: str | None = None,
    saved_view: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    clauses, params = _saved_view_clauses(saved_view)
    join = ""
    select_extra = ""
    if q:
        join = "JOIN documents_fts ON documents_fts.rowid = documents.id"
        # column index -1 lets FTS5 pick whichever column actually matched
        # (correspondent/doc_type/summary/summary_sk/summary_en/original_filename/full_text)
        # instead of guessing one in advance.
        select_extra = ", snippet(documents_fts, -1, '<<', '>>', ' ... ', 20) AS match_snippet"
        clauses.append("documents_fts MATCH ?")
        params.append(q)
    if correspondent:
        clauses.append("correspondent = ?")
        params.append(correspondent)
    if doc_type:
        clauses.append("doc_type = ?")
        params.append(doc_type)
    if review_status:
        clauses.append("review_status = ?")
        params.append(review_status)

    where = f"WHERE {' AND '.join(f'({clause})' for clause in clauses)}" if clauses else ""
    rows = execute(
        f"SELECT documents.*{select_extra} FROM documents {join} {where} "
        f"ORDER BY documents.created_at DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return [_document_payload(r) for r in rows]


@router.get("")
def list_documents(
    q: str | None = None,
    correspondent: str | None = None,
    doc_type: str | None = None,
    review_status: str | None = None,
    saved_view: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    return _list_documents_query(
        q=q,
        correspondent=correspondent,
        doc_type=doc_type,
        review_status=review_status,
        saved_view=saved_view,
        limit=limit,
        offset=offset,
    )


@router.get("/facets")
def get_facets():
    correspondents = execute(
        """SELECT correspondent, COUNT(*) AS count FROM documents
           WHERE status = 'processed' GROUP BY correspondent ORDER BY count DESC LIMIT 20"""
    ).fetchall()
    doc_types = execute(
        """SELECT doc_type, COUNT(*) AS count FROM documents
           WHERE status = 'processed' GROUP BY doc_type ORDER BY count DESC LIMIT 20"""
    ).fetchall()
    failed_count = execute(
        "SELECT COUNT(*) AS count FROM documents WHERE status = 'failed'"
    ).fetchone()["count"]
    pending_count = execute(
        "SELECT COUNT(*) AS count FROM documents WHERE status = 'pending'"
    ).fetchone()["count"]
    review_counts = execute(
        """SELECT review_status, COUNT(*) AS count FROM documents
           GROUP BY review_status ORDER BY count DESC"""
    ).fetchall()
    duplicate_count = execute(
        """SELECT COUNT(DISTINCT document_id) AS count
           FROM document_duplicate_candidates WHERE status = 'open'"""
    ).fetchone()["count"]
    return {
        "correspondents": [_row_to_dict(r) for r in correspondents],
        "doc_types": [_row_to_dict(r) for r in doc_types],
        "failed_count": failed_count,
        "pending_count": pending_count,
        "review_counts": [_row_to_dict(r) for r in review_counts],
        "duplicate_count": duplicate_count,
    }


def _saved_view_count(key: str) -> int:
    clauses, params = _saved_view_clauses(key)
    where = f"WHERE {' AND '.join(f'({clause})' for clause in clauses)}" if clauses else ""
    return execute(
        f"SELECT COUNT(*) AS count FROM documents {where}",
        tuple(params),
    ).fetchone()["count"]


@router.get("/saved-views")
def list_saved_views():
    rows = execute("SELECT * FROM saved_views ORDER BY sort_order, label").fetchall()
    return [
        {
            **_row_to_dict(row),
            "query": json.loads(row["query_json"]),
            "count": _saved_view_count(row["key"]),
        }
        for row in rows
    ]


@router.get("/expiring")
def get_expiring_documents(days: int = 60):
    """Documents whose expiry_date (insurance renewal, contract/ID expiry --
    whatever the AI could find) falls within the next `days`. Includes
    already-overdue ones (expiry_date < today) so nothing silently slips by
    unnoticed."""
    horizon = (date.today() + timedelta(days=days)).isoformat()
    rows = execute(
        """SELECT * FROM documents
           WHERE status = 'processed'
             AND expiry_date IS NOT NULL
             AND expiry_dismissed_at IS NULL
             AND expiry_date <= ?
           ORDER BY expiry_date ASC""",
        (horizon,),
    ).fetchall()
    return [_document_payload(r) for r in rows]


def _parse_ids(ids: str) -> list[int]:
    try:
        return [int(part) for part in ids.split(",") if part.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Neplatny zoznam id") from exc


@router.get("/export")
def export_documents(format: str = "json", q: str | None = None, ids: str | None = None):
    if ids:
        id_list = _parse_ids(ids)
        placeholders = ",".join("?" * len(id_list))
        rows = [
            _row_to_dict(r)
            for r in execute(
                f"SELECT * FROM documents WHERE id IN ({placeholders})", tuple(id_list)
            ).fetchall()
        ]
    else:
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
    return _document_payload(row)


@router.get("/{document_id}/events")
def get_document_events(document_id: int):
    if execute("SELECT id FROM documents WHERE id = ?", (document_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")
    rows = execute(
        """SELECT * FROM document_events
           WHERE document_id = ?
           ORDER BY created_at DESC, id DESC""",
        (document_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


@router.get("/{document_id}/duplicates")
def get_document_duplicates(document_id: int):
    if execute("SELECT id FROM documents WHERE id = ?", (document_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")
    rows = execute(
        """SELECT dc.*, d.id AS match_id, d.original_filename, d.correspondent, d.doc_type, d.doc_date,
                  d.amount_value, d.amount_currency
           FROM document_duplicate_candidates dc
           JOIN documents d ON d.id = CASE
               WHEN dc.document_id = ? THEN dc.candidate_id
               ELSE dc.document_id
           END
           WHERE dc.status = 'open' AND (dc.document_id = ? OR dc.candidate_id = ?)
           ORDER BY dc.score DESC, dc.created_at DESC""",
        (document_id, document_id, document_id),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


@router.post("/duplicates/{candidate_id}/status")
def update_duplicate_candidate(candidate_id: int, payload: dict):
    status = payload.get("status")
    if status not in {"open", "ignored", "confirmed"}:
        raise HTTPException(status_code=422, detail="Neplatny duplicate status")
    row = execute(
        "SELECT * FROM document_duplicate_candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Duplikatovy warning nenajdeny")
    execute(
        """UPDATE document_duplicate_candidates
           SET status = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (status, candidate_id),
    )
    for document_id in (row["document_id"], row["candidate_id"]):
        add_document_event(
            document_id,
            "duplicate_status",
            f"Duplikatovy warning #{candidate_id} oznaceny ako {status}",
            actor="user",
        )
    return {"ok": True, "status": status}


@router.post("/{document_id}/expiry-dismissal")
def dismiss_expiry_alert(document_id: int):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")
    execute(
        "UPDATE documents SET expiry_dismissed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
        (document_id,),
    )
    add_document_event(document_id, "expiry_dismissed", "Expiracne upozornenie oznacene ako vybavene", actor="user")
    return get_document(document_id)


@router.delete("/{document_id}/expiry-dismissal")
def restore_expiry_alert(document_id: int):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")
    execute(
        "UPDATE documents SET expiry_dismissed_at = NULL, updated_at = datetime('now') WHERE id = ?",
        (document_id,),
    )
    add_document_event(document_id, "expiry_restored", "Expiracne upozornenie obnovene", actor="user")
    return get_document(document_id)


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

    media_type = _download_mime_type(path, row["mime_type"])
    disposition = "attachment" if download or media_type in DOWNLOAD_ONLY_MIME_TYPES else "inline"
    return FileResponse(
        path,
        media_type=media_type,
        filename=row["original_filename"],
        content_disposition_type=disposition,
    )


@router.patch("/{document_id}")
def update_document(document_id: int, payload: dict):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")

    allowed = {
        "correspondent", "doc_type", "doc_date", "expiry_date", "expiry_dismissed_at",
        "amount_value", "amount_currency", "summary", "summary_sk", "summary_en",
        "review_status", "notify_recurrence",
    }
    fields = {k: v for k, v in payload.items() if k in allowed}
    if "summary" in fields and "summary_sk" not in fields:
        fields["summary_sk"] = fields["summary"]
    if "expiry_date" in fields and fields["expiry_date"] != row["expiry_date"]:
        # A corrected expiry date invalidates any earlier Telegram notification
        # sent for the old one -- otherwise expiry_notifier.py would never
        # ping again about a document it already (incorrectly) notified for.
        fields["expiry_notified_at"] = None
    if "notify_recurrence" in fields and fields["notify_recurrence"] != row["notify_recurrence"]:
        recurrence = fields["notify_recurrence"]
        if recurrence in RECURRENCE_MONTHS:
            fields["next_recurrence_at"] = _add_months(date.today(), RECURRENCE_MONTHS[recurrence]).isoformat()
        else:
            fields["next_recurrence_at"] = None
    if fields:
        changes = {
            key: {"from": row[key], "to": value}
            for key, value in fields.items()
            if row[key] != value
        }
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        execute(
            f"UPDATE documents SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            (*fields.values(), document_id),
        )
        if changes:
            add_document_event(
                document_id,
                "document_updated",
                "Metadata dokumentu upravene",
                actor="user",
                metadata={"changes": changes},
            )
    return get_document(document_id)


@router.post("/{document_id}/review-status")
def update_review_status(document_id: int, payload: dict):
    review_status = payload.get("review_status")
    allowed = {"na_kontrolu", "vybavene", "zaplatit", "zamietnute", "archiv"}
    if review_status not in allowed:
        raise HTTPException(status_code=422, detail="Neplatny review status")
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")
    execute(
        "UPDATE documents SET review_status = ?, updated_at = datetime('now') WHERE id = ?",
        (review_status, document_id),
    )
    add_document_event(
        document_id,
        "review_status",
        f"Review stav zmeneny na {review_status}",
        actor="user",
        metadata={"from": row["review_status"], "to": review_status},
    )
    return get_document(document_id)


@router.post("/{document_id}/retry")
def retry_document(document_id: int):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")
    if row["status"] not in ("failed", "pending"):
        raise HTTPException(status_code=409, detail="Retry je dostupny len pre failed alebo pending dokumenty")
    path = Path(row["stored_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Povodny subor sa na disku nenasiel")

    add_document_event(document_id, "retry_started", "Spusteny manualny retry dokumentu", actor="user")
    from ...ingest.pipeline import reprocess_document

    result = reprocess_document(document_id)
    add_document_event(
        document_id,
        "retry_finished",
        f"Manualny retry skoncil stavom {result.get('status')}",
        actor="system",
        metadata=result,
    )
    return result


@router.delete("")
def bulk_delete_documents(ids: str):
    id_list = _parse_ids(ids)
    if not id_list:
        raise HTTPException(status_code=422, detail="Ziadne id na zmazanie")
    placeholders = ",".join("?" * len(id_list))
    rows = execute(f"SELECT stored_path FROM documents WHERE id IN ({placeholders})", tuple(id_list)).fetchall()
    for row in rows:
        _delete_stored_file(row["stored_path"])
    execute(f"DELETE FROM documents WHERE id IN ({placeholders})", tuple(id_list))
    return {"deleted": len(id_list)}


@router.delete("/{document_id}")
def delete_document(document_id: int):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument nenajdeny")
    _delete_stored_file(row["stored_path"])
    execute("DELETE FROM documents WHERE id = ?", (document_id,))
    return {"ok": True}
