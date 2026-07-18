import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from . import crypto, telegram
from .db import execute
from .settings_store import get_setting

logger = logging.getLogger("muninn.expiry_notifier")

# Cheap check (one SQLite query, at most one Telegram call) -- no need to
# poll more often than a few times a day for something that changes on the
# scale of days.
CHECK_INTERVAL_SECONDS = 6 * 3600


async def run_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(_check_once)
        except Exception:
            logger.exception("Expiry notifier zlyhal, skusim znova neskor")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def _check_once() -> None:
    config = get_setting("telegram", {})
    if not config.get("enabled") or not config.get("bot_token_encrypted") or not config.get("chat_id"):
        return

    days = config.get("notify_days_before", 30)
    horizon = (date.today() + timedelta(days=days)).isoformat()
    rows = execute(
        """SELECT * FROM documents
           WHERE status = 'processed'
             AND expiry_date IS NOT NULL
             AND expiry_dismissed_at IS NULL
             AND expiry_notified_at IS NULL
             AND expiry_date <= ?
           ORDER BY expiry_date ASC""",
        (horizon,),
    ).fetchall()
    if not rows:
        return

    bot_token = crypto.decrypt(config["bot_token_encrypted"])
    chat_id = config["chat_id"]
    lines = [f"- {row['correspondent']} ({row['doc_type']}): plati do {row['expiry_date']}" for row in rows]
    text = "Muninn - blizi sa expiracia:\n" + "\n".join(lines)

    ok, message = telegram.send_message(bot_token, chat_id, text)
    if not ok:
        logger.warning("Telegram notifikacia zlyhala: %s", message)
        return

    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        execute("UPDATE documents SET expiry_notified_at = ? WHERE id = ?", (now, row["id"]))
    logger.info("Telegram: odoslana notifikacia o %d expirujucich dokumentoch", len(rows))
