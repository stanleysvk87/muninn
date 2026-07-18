import asyncio
import calendar
import logging
from datetime import date, datetime, timedelta, timezone

from . import crypto, telegram
from .audit import add_document_event
from .db import execute
from .settings_store import get_setting

logger = logging.getLogger("muninn.expiry_notifier")

# Cheap check (one or two SQLite queries, at most a couple Telegram calls) --
# no need to poll more often than a few times a day for something that
# changes on the scale of days.
CHECK_INTERVAL_SECONDS = 6 * 3600

RECURRENCE_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}

# Telegram has no per-request Accept-Language -- these background pushes
# pick a language from the "telegram.notification_language" setting
# (configured once in Settings) instead of the browser's i18n toggle.
_EXPIRING_HEADER = {
    "sk": "Muninn - blizi sa expiracia:",
    "en": "Muninn - upcoming expiry:",
}
_EXPIRING_LINE = {
    "sk": "- {correspondent} ({doc_type}): plati do {expiry_date}",
    "en": "- {correspondent} ({doc_type}): valid until {expiry_date}",
}
_RECURRENCE_TEXT = {
    "sk": "Muninn - pravidelna pripomienka ({recurrence}):\n- {correspondent} ({doc_type})",
    "en": "Muninn - recurring reminder ({recurrence}):\n- {correspondent} ({doc_type})",
}


def _notification_language() -> str:
    language = get_setting("telegram", {}).get("notification_language", "sk")
    return language if language in _EXPIRING_HEADER else "sk"


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


async def run_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(_check_once)
        except Exception:
            logger.exception("Expiry notifier zlyhal, skusim znova neskor")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def _telegram_credentials() -> tuple[str, str] | None:
    config = get_setting("telegram", {})
    if not config.get("enabled") or not config.get("bot_token_encrypted") or not config.get("chat_id"):
        return None
    return crypto.decrypt(config["bot_token_encrypted"]), config["chat_id"]


def _check_once() -> None:
    creds = _telegram_credentials()
    if creds is None:
        return
    bot_token, chat_id = creds
    _check_expiring(bot_token, chat_id)
    _check_recurrences(bot_token, chat_id)


def _check_expiring(bot_token: str, chat_id: str) -> None:
    config = get_setting("telegram", {})
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

    language = _notification_language()
    lines = [
        _EXPIRING_LINE[language].format(
            correspondent=row["correspondent"], doc_type=row["doc_type"], expiry_date=row["expiry_date"]
        )
        for row in rows
    ]
    text = _EXPIRING_HEADER[language] + "\n" + "\n".join(lines)

    ok, message = telegram.send_message(bot_token, chat_id, text)
    if not ok:
        logger.warning("Telegram expiry notifikacia zlyhala: %s", message)
        return

    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        execute("UPDATE documents SET expiry_notified_at = ? WHERE id = ?", (now, row["id"]))
    logger.info("Telegram: odoslana notifikacia o %d expirujucich dokumentoch", len(rows))


def _check_recurrences(bot_token: str, chat_id: str) -> None:
    """Some documents (insurance, subscriptions) warrant a recurring check-in
    independent of any expiry_date -- e.g. "remind me every quarter to look
    at this policy" -- rather than a single one-off expiry ping."""
    today = date.today().isoformat()
    rows = execute(
        """SELECT * FROM documents
           WHERE status = 'processed'
             AND notify_recurrence IS NOT NULL
             AND next_recurrence_at IS NOT NULL
             AND next_recurrence_at <= ?
           ORDER BY next_recurrence_at ASC""",
        (today,),
    ).fetchall()
    if not rows:
        return

    language = _notification_language()
    for row in rows:
        text = _RECURRENCE_TEXT[language].format(
            recurrence=row["notify_recurrence"], correspondent=row["correspondent"], doc_type=row["doc_type"]
        )
        ok, message = telegram.send_message(bot_token, chat_id, text)
        if not ok:
            logger.warning("Telegram recurrence notifikacia zlyhala pre #%s: %s", row["id"], message)
            continue

        months = RECURRENCE_MONTHS.get(row["notify_recurrence"], 1)
        next_at = _add_months(date.today(), months).isoformat()
        execute("UPDATE documents SET next_recurrence_at = ? WHERE id = ?", (next_at, row["id"]))
        add_document_event(
            row["id"],
            "recurrence_notified",
            f"Odoslana pravidelna pripomienka ({row['notify_recurrence']}), dalsia {next_at}",
        )
        logger.info("Telegram: odoslana pravidelna pripomienka pre #%s, dalsia %s", row["id"], next_at)
