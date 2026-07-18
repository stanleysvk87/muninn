import asyncio
import email
import imaplib
import logging
import re
import shutil
import tempfile
from email.header import decode_header, make_header
from pathlib import Path

from .. import crypto
from ..settings_store import get_setting, set_setting
from . import pipeline

logger = logging.getLogger("muninn.mail")

DEFAULT_POLL_INTERVAL_SECONDS = 300
MAX_UID_ATTEMPTS = 3
MIN_MAIL_IMAGE_ATTACHMENT_BYTES = 50_000


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

    # Track progress by UID (our own watermark) rather than the \Seen flag --
    # \Seen can end up set by something other than us (e.g. server-side spam
    # scanning previewing the message), which would silently hide a message
    # from a SEARCH UNSEEN poll before we ever got a chance to look at it.
    # This bit us in production: a real forwarded mail arrived already \Seen
    # and was never picked up.
    last_uid = get_setting("mail_last_uid", 0)

    conn = imaplib.IMAP4_SSL(config["host"], config.get("port", 993))
    try:
        conn.login(config["username"], password)
        conn.select("INBOX")
        status, data = conn.uid("search", None, f"UID {last_uid + 1}:*")
        if status != "OK":
            logger.warning("Mail poll: UID search zlyhalo (status=%s)", status)
            return

        # IMAP quirk: a "X:*" range where X is past the highest existing UID
        # still returns the highest UID instead of nothing -- filter those out.
        uids = sorted({int(u) for u in data[0].split() if int(u) > last_uid})
        if not uids:
            return

        logger.info("Mail poll: %d novych sprav (UID > %d)", len(uids), last_uid)
        failed_uids = get_setting("mail_failed_uids", {})
        for uid in uids:
            result = _process_message(conn, uid)
            if result.get("ok"):
                failed_uids.pop(str(uid), None)
                set_setting("mail_failed_uids", failed_uids)
                last_uid = uid
                set_setting("mail_last_uid", last_uid)
                continue

            entry = failed_uids.get(str(uid), {})
            attempts = int(entry.get("attempts") or 0) + 1
            failed_uids[str(uid)] = {
                "attempts": attempts,
                "last_error": result.get("error") or "nezname zlyhanie",
                "document_id": result.get("document_id"),
            }
            set_setting("mail_failed_uids", failed_uids)

            if attempts >= MAX_UID_ATTEMPTS:
                logger.error(
                    "Mail poll: UID %d zlyhal %dx, presuvam do dead-letter a posuvam watermark",
                    uid,
                    attempts,
                )
                last_uid = uid
                set_setting("mail_last_uid", last_uid)
                continue

            logger.warning(
                "Mail poll: UID %d zlyhal (pokus %d/%d), watermark zostava na %d",
                uid,
                attempts,
                MAX_UID_ATTEMPTS,
                last_uid,
            )
            break
    finally:
        conn.logout()


def _process_message(conn: imaplib.IMAP4_SSL, uid: int) -> dict:
    status, msg_data = conn.uid("fetch", str(uid), "(RFC822)")
    if status != "OK" or not msg_data or msg_data[0] is None:
        logger.warning("Mail poll: fetch UID %d zlyhalo", uid)
        return {"ok": False, "error": "fetch zlyhal"}

    message = email.message_from_bytes(msg_data[0][1])
    found_attachment = False
    results = []
    for part in message.walk():
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if not filename or not payload:
            continue
        if not _should_process_part(part, filename, payload):
            logger.info("Mail poll: UID %d preskakujem inline asset %s", uid, filename)
            continue
        found_attachment = True

        tmp_dir = Path(tempfile.mkdtemp(prefix="muninn-mail-"))
        tmp_path = tmp_dir / _safe_filename(filename, fallback=f"mail-{uid}.bin")
        tmp_path.write_bytes(payload)
        try:
            results.append(pipeline.process(tmp_path, source="mail", source_detail=f"uid:{uid}"))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    if not found_attachment:
        results.append(_process_body_only(message, uid))

    failed = [r for r in results if r and r.get("status") == "failed"]
    if failed:
        first = failed[0]
        return {
            "ok": False,
            "document_id": first.get("document_id"),
            "error": first.get("error_message") or "spracovanie dokumentu zlyhalo",
        }
    return {"ok": True}


def _decode_subject(raw: str | None) -> str:
    if not raw:
        return "bez-predmetu"
    return str(make_header(decode_header(raw)))


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "mail"


def _safe_filename(raw: str, fallback: str) -> str:
    try:
        decoded = str(make_header(decode_header(raw)))
    except (LookupError, UnicodeDecodeError, ValueError):
        decoded = raw
    name = Path(decoded.replace("\\", "/")).name.strip().strip(".")
    name = re.sub(r"[\x00-\x1f]+", "", name)
    name = re.sub(r"[/:]+", "-", name)
    return name[:160] or fallback


def _should_process_part(part: "email.message.Message", filename: str, payload: bytes) -> bool:
    content_type = part.get_content_type() or ""
    disposition = (part.get_content_disposition() or "").lower()
    content_id = part.get("Content-ID")

    if not content_type.startswith("image/"):
        return True

    if disposition == "attachment" and len(payload) >= MIN_MAIL_IMAGE_ATTACHMENT_BYTES:
        return True

    # HTML emails routinely carry logos, spacer bars, payment icons and status
    # images as named MIME parts. They have filenames, but they are not user
    # documents and should not pollute the archive.
    if disposition == "inline" or content_id or len(payload) < MIN_MAIL_IMAGE_ATTACHMENT_BYTES:
        return False

    return True


def _process_body_only(message: "email.message.Message", uid: int) -> dict:
    """Some senders (e.g. order-confirmation systems) put everything of value
    straight in the HTML/plain body with no attachment at all -- seen in
    production with a Bidfood order-status mail. Archive the body itself as
    a document instead of silently dropping content like this."""
    body_bytes: bytes | None = None
    suffix = ".txt"
    for content_type, ext in (("text/html", ".html"), ("text/plain", ".txt")):
        for part in message.walk():
            if part.get_content_type() != content_type:
                continue
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                try:
                    text = payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    text = payload.decode("utf-8", errors="replace")
                body_bytes = text.encode("utf-8")
                suffix = ext
                break
        if body_bytes:
            break

    if not body_bytes:
        logger.info("Mail poll: UID %d nema ani prilohu ani citatelne telo, preskakujem", uid)
        return {"status": "processed", "duplicate": False}

    subject = _decode_subject(message.get("Subject"))
    filename = f"{_slugify(subject)[:80]}{suffix}"

    tmp_dir = Path(tempfile.mkdtemp(prefix="muninn-mailbody-"))
    tmp_path = tmp_dir / filename
    tmp_path.write_bytes(body_bytes)
    try:
        return pipeline.process(tmp_path, source="mail", source_detail=f"uid:{uid} (telo spravy, bez prilohy)")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
