import asyncio
import logging

from .db import execute

logger = logging.getLogger("muninn.queue_retry")

# Rate limits/outages typically clear on the order of minutes to hours --
# no need to hammer a still-down provider more often than this. Each check
# is cheap (the providers themselves fail fast on auth/rate-limit errors,
# no real API cost), so a flat interval is enough; no per-document backoff.
CHECK_INTERVAL_SECONDS = 10 * 60


async def run_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(_check_once)
        except Exception:
            logger.exception("Queue retry zlyhal, skusim znova neskor")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def _check_once() -> None:
    rows = execute(
        "SELECT id FROM documents WHERE status = 'pending' ORDER BY created_at ASC"
    ).fetchall()
    if not rows:
        return

    from .ingest.pipeline import reprocess_document

    logger.info("Queue retry: skusam %d dokumentov vo fronte", len(rows))
    for row in rows:
        result = reprocess_document(row["id"])
        if result.get("status") == "processed":
            logger.info("Queue retry: dokument #%s uspesne spracovany", row["id"])
        elif result.get("status") == "failed":
            logger.info(
                "Queue retry: dokument #%s teraz zlyhal natrvalo (provider dostupny, obsah nie je citatelny)",
                row["id"],
            )
