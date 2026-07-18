import json

from .db import execute


def add_document_event(
    document_id: int,
    event_type: str,
    message: str,
    *,
    actor: str = "system",
    metadata: dict | None = None,
) -> None:
    execute(
        """INSERT INTO document_events
             (document_id, event_type, message, actor, metadata_json, created_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))""",
        (
            document_id,
            event_type,
            message,
            actor,
            json.dumps(metadata, ensure_ascii=False) if metadata else None,
        ),
    )


def start_ingest_job(source: str, source_detail: str | None, original_filename: str) -> int:
    cur = execute(
        """INSERT INTO ingest_jobs
             (source, source_detail, original_filename, status, started_at)
           VALUES (?, ?, ?, 'processing', datetime('now'))""",
        (source, source_detail, original_filename),
    )
    return cur.lastrowid


def finish_ingest_job(
    job_id: int,
    *,
    status: str,
    document_id: int | None = None,
    duplicate: bool = False,
    ai_provider: str | None = None,
    error_message: str | None = None,
) -> None:
    execute(
        """UPDATE ingest_jobs
           SET status = ?, document_id = ?, duplicate = ?, ai_provider = ?,
               error_message = ?, finished_at = datetime('now')
           WHERE id = ?""",
        (status, document_id, 1 if duplicate else 0, ai_provider, error_message, job_id),
    )
