import csv
import io
import json
import sqlite3
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from ...audit import add_deletion_record, add_document_event
from ...db import execute
from ...errors import api_error
from ...expiry_notifier import RECURRENCE_MONTHS, _add_months

router = APIRouter(prefix="/documents", tags=["documents"])

EXPORT_FIELDS = [
    "id", "correspondent", "doc_type", "doc_date", "amount_value",
    "amount_currency", "summary", "summary_sk", "summary_en", "original_filename", "stored_path",
]

# Allowlist, deliberately NOT a denylist: archived documents are
# attacker-influenced content (the IMAP poller archives an HTML mail body
# verbatim as .html, and anyone who can mail the ingest address controls
# it), so a MIME type nobody thought about must default to "download",
# never to "render on Muninn's own origin". Rendering text/html or
# image/svg+xml inline used to give such a document script execution on the
# app origin -> read of the non-httponly muninn_csrf cookie -> full
# authenticated API access (export/delete of the whole archive).
INLINE_SAFE_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "image/png",
    "image/jpeg",
    "image/pjpeg",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/avif",
    "image/heic",
    "image/heif",
}
# Extra belt-and-braces for everything served as an attachment: even if a
# browser were to ignore Content-Disposition, a fully sandboxed response
# (unique opaque origin, no scripts) cannot touch Muninn's cookies.
ATTACHMENT_CSP = "default-src 'none'; sandbox"
EXTENSION_MIME_TYPES = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
}


def _fts_query(raw: str) -> str | None:
    """Turn whatever the user typed into a syntactically valid FTS5 query.

    documents_fts MATCH used to get the raw string, so any input carrying
    FTS5 syntax blew up with a sqlite3.OperationalError -> unhandled 500.
    Verified failures on completely ordinary input: 'T-Mobile' (parsed as
    column filter -> "no such column: Mobile"), "it's", a lone double quote,
    a trailing 'OR'. Slovak correspondent names are full of hyphens and the
    search box fires on every keystroke, so this happened during normal use.

    Every whitespace-separated token becomes a quoted FTS5 phrase (with
    embedded quotes doubled, the FTS5 escape), joined implicitly by AND.
    That makes the query total -- no input can be a syntax error -- at the
    cost of not exposing FTS5 boolean operators to the user, which was never
    a documented feature of the search box anyway.
    """
    tokens = [token.replace('"', '""') for token in raw.split() if token.strip('"')]
    if not tokens:
        return None
    return " ".join(f'"{token}"' for token in tokens)


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


# Columns that hold the full document transcription and the raw AI answer.
# A single one of them can be hundreds of KB, so list/facet-style responses
# drop them: the 50-row dashboard page used to ship 50 complete
# transcriptions plus 50 raw AI responses on every single load. The
# single-document endpoint still returns them in full.
HEAVY_COLUMNS = ("full_text", "ai_raw_response")


def _document_payload(row, include_heavy: bool = True) -> dict:
    data = _row_to_dict(row)
    if not include_heavy:
        for column in HEAVY_COLUMNS:
            data.pop(column, None)
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
        raise api_error(409, "stored_path_not_a_file")
    try:
        path.unlink()
    except OSError as exc:
        raise api_error(500, "file_delete_failed", error=str(exc)) from exc


def _saved_view_clauses(saved_view: str | None) -> tuple[list[str], list]:
    if not saved_view:
        return [], []
    view = execute("SELECT query_json FROM saved_views WHERE key = ?", (saved_view,)).fetchone()
    if view is None:
        raise api_error(404, "saved_view_not_found")
    try:
        query = json.loads(view["query_json"])
    except json.JSONDecodeError as exc:
        raise api_error(500, "saved_view_invalid_config") from exc

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
    include_heavy: bool = False,
) -> list[dict]:
    clauses, params = _saved_view_clauses(saved_view)
    join = ""
    select_extra = ""
    if q:
        match_expression = _fts_query(q)
        if match_expression is None:
            # The user typed only punctuation/quotes -- nothing to match on.
            return []
        join = "JOIN documents_fts ON documents_fts.rowid = documents.id"
        # column index -1 lets FTS5 pick whichever column actually matched
        # (correspondent/doc_type/summary/summary_sk/summary_en/original_filename/full_text)
        # instead of guessing one in advance.
        select_extra = ", snippet(documents_fts, -1, '<<', '>>', ' ... ', 20) AS match_snippet"
        clauses.append("documents_fts MATCH ?")
        params.append(match_expression)
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
    try:
        rows = execute(
            f"SELECT documents.*{select_extra} FROM documents {join} {where} "
            f"ORDER BY documents.created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        # _fts_query() should make this unreachable; a 422 beats a 500 if
        # some future FTS5 edge case still slips through.
        raise api_error(422, "invalid_search_query") from exc
    return [_document_payload(r, include_heavy=include_heavy) for r in rows]


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
        limit=min(max(limit, 1), 500),
        offset=max(offset, 0),
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
    return [_document_payload(r, include_heavy=False) for r in rows]


def _parse_ids(ids: str) -> list[int]:
    try:
        return [int(part) for part in ids.split(",") if part.strip()]
    except ValueError as exc:
        raise api_error(422, "invalid_id_list") from exc


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
        # An export deliberately keeps the heavy columns (that is the point of
        # an export), unlike the dashboard list.
        rows = _list_documents_query(q=q, limit=10000, offset=0, include_heavy=True)

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
        # Built on disk, not in a BytesIO: a full-archive export used to
        # materialise every document in RAM at once before a single byte was
        # sent, which on an 8GB SBC is a straightforward way to OOM the
        # service. FileResponse streams it and the BackgroundTask deletes the
        # temp file once the response has been fully sent.
        tmp = tempfile.NamedTemporaryFile(prefix="muninn-export-", suffix=".zip", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        try:
            with zipfile.ZipFile(tmp_path, "w") as zf:
                for row in rows:
                    stored_path = Path(row["stored_path"])
                    if stored_path.is_file():
                        zf.write(stored_path, arcname=f"{row['id']}_{stored_path.name}")
                zf.writestr("manifest.json", json.dumps(rows, indent=2))
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        return FileResponse(
            tmp_path,
            media_type="application/zip",
            filename="documents.zip",
            background=BackgroundTask(tmp_path.unlink, missing_ok=True),
        )

    raise api_error(400, "unknown_export_format")


@router.get("/{document_id}")
def get_document(document_id: int):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise api_error(404, "document_not_found")
    return _document_payload(row)


@router.get("/{document_id}/events")
def get_document_events(document_id: int):
    if execute("SELECT id FROM documents WHERE id = ?", (document_id,)).fetchone() is None:
        raise api_error(404, "document_not_found")
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
        raise api_error(404, "document_not_found")
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
        raise api_error(422, "invalid_duplicate_status")
    row = execute(
        "SELECT * FROM document_duplicate_candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise api_error(404, "duplicate_warning_not_found")
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
        raise api_error(404, "document_not_found")
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
        raise api_error(404, "document_not_found")
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
        raise api_error(404, "document_not_found")

    path = Path(row["stored_path"])
    if not path.is_file():
        raise api_error(404, "file_not_found_on_disk")

    media_type = _download_mime_type(path, row["mime_type"])
    inline = not download and media_type.split(";")[0].strip().lower() in INLINE_SAFE_MIME_TYPES
    headers = {} if inline else {"Content-Security-Policy": ATTACHMENT_CSP}
    return FileResponse(
        path,
        media_type=media_type,
        filename=row["original_filename"],
        content_disposition_type="inline" if inline else "attachment",
        headers=headers,
    )


@router.patch("/{document_id}")
def update_document(document_id: int, payload: dict):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise api_error(404, "document_not_found")

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
        raise api_error(422, "invalid_review_status")
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise api_error(404, "document_not_found")
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
        raise api_error(404, "document_not_found")
    if row["status"] not in ("failed", "pending"):
        raise api_error(409, "retry_not_allowed")
    path = Path(row["stored_path"])
    if not path.is_file():
        raise api_error(404, "original_file_not_found")

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


def _actor(request: Request) -> str:
    user = getattr(request.state, "user", None)
    try:
        return user["username"] if user is not None else "user"
    except (KeyError, IndexError, TypeError):
        return "user"


@router.delete("")
def bulk_delete_documents(ids: str, request: Request):
    """Bulk delete used to unlink every file first and only then issue a
    single DELETE. One bad stored_path in the middle of the batch (an
    api_error out of _delete_stored_file) aborted the request before the
    DELETE ever ran: the already-unlinked files were gone, every DB row
    survived, and the caller got told nothing was deleted. Now each file is
    removed best-effort, the rows always go, and the response reports what
    actually happened instead of just echoing the number of ids sent."""
    id_list = _parse_ids(ids)
    if not id_list:
        raise api_error(422, "no_ids_to_delete")
    placeholders = ",".join("?" * len(id_list))
    rows = execute(
        f"SELECT * FROM documents WHERE id IN ({placeholders})", tuple(id_list)
    ).fetchall()
    if not rows:
        return {"deleted": 0, "file_errors": []}

    actor = _actor(request)
    file_errors: list[dict] = []
    for row in rows:
        error_message = None
        try:
            _delete_stored_file(row["stored_path"])
            removed = True
        except HTTPException as exc:
            removed = False
            detail = exc.detail
            error_message = detail.get("message") if isinstance(detail, dict) else str(detail)
            file_errors.append({"id": row["id"], "error": error_message})
        add_deletion_record(row, actor=actor, file_removed=removed, error_message=error_message)

    deleted_ids = [row["id"] for row in rows]
    deleted_placeholders = ",".join("?" * len(deleted_ids))
    cur = execute(
        f"DELETE FROM documents WHERE id IN ({deleted_placeholders})", tuple(deleted_ids)
    )
    return {"deleted": cur.rowcount, "file_errors": file_errors}


@router.delete("/{document_id}")
def delete_document(document_id: int, request: Request):
    row = execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if row is None:
        raise api_error(404, "document_not_found")
    # Single-document delete stays fail-loud: if the file can't be removed,
    # nothing is deleted at all, so "delete" never half-succeeds silently.
    _delete_stored_file(row["stored_path"])
    add_deletion_record(row, actor=_actor(request), file_removed=True)
    execute("DELETE FROM documents WHERE id = ?", (document_id,))
    return {"ok": True}
