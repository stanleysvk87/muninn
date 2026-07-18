import asyncio
import email
import imaplib
import logging
import tempfile
from pathlib import Path

from .. import crypto
from ..settings_store import get_setting
from . import pipeline

logger = logging.getLogger("muninn.mail")

DEFAULT_POLL_INTERVAL_SECONDS = 300


async def run_forever() -> None:
    logged_disabled_once = False
    while True:
        config = get_setting("mail", {})
        if not config.get("enabled") or not config.get("host"):
            if not logged_disabled_once:
                logger.info("Mail ingestion vypnute alebo nenastavene - preskakujem")
                logged_disabled_once = True
            await asyncio.sleep(DEFAULT_POLL_INTERVAL_SECONDS)
            continue

        logged_disabled_once = False
        try:
            await asyncio.to_thread(_poll_once, config)
        except Exception:
            logger.exception("Mail poll zlyhal, skusim znova o chvilu")

        await asyncio.sleep(config.get("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS))


def _poll_once(config: dict) -> None:
    password_encrypted = config.get("password_encrypted")
    password = crypto.decrypt(password_encrypted) if password_encrypted else config.get("password", "")

    conn = imaplib.IMAP4_SSL(config["host"], config.get("port", 993))
    try:
        conn.login(config["username"], password)
        conn.select("INBOX")
        status, data = conn.search(None, "UNSEEN")
        if status != "OK":
            return
        for uid in data[0].split():
            _process_message(conn, uid)
    finally:
        conn.logout()


def _process_message(conn: imaplib.IMAP4_SSL, uid: bytes) -> None:
    status, msg_data = conn.fetch(uid, "(RFC822)")
    if status != "OK":
        return

    message = email.message_from_bytes(msg_data[0][1])
    for part in message.walk():
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if not filename or not payload:
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        try:
            pipeline.process(tmp_path, source="mail", source_detail=f"uid:{uid.decode()}")
        finally:
            tmp_path.unlink(missing_ok=True)

    conn.store(uid, "+FLAGS", "\\Seen")
