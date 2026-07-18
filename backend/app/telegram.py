"""
Telegram delivery via plain HTTP requests to the Bot API (no SDK dependency).
Ported from ~/projects/camera-ai-telegram/app/telegram.py -- same house
pattern used for that project's camera-alert notifications.
"""
import logging

import httpx

logger = logging.getLogger("muninn.telegram")

TELEGRAM_TIMEOUT_SECONDS = 10.0

# httpx logs "HTTP Request: GET https://api.telegram.org/bot<TOKEN>/getMe" at
# INFO level by default, which would otherwise leak the bot token in
# plaintext to container logs on every request. Every Telegram call in this
# module embeds the token in the URL, so silence it here.
logging.getLogger("httpx").setLevel(logging.WARNING)


def is_configured(bot_token: str, chat_id: str) -> bool:
    return bool(bot_token and chat_id)


def sanitize_bot_token(raw: str) -> str:
    """Strip whitespace, wrapping quote characters, and an optional leading
    "bot" prefix - all artifacts seen from copy-pasting or shell-quoting
    mistakes rather than legitimate token content (real tokens are only
    alphanumeric plus `:`, `_`, `-`)."""
    token = (raw or "").strip()
    token = token.strip("'\"`")
    if token[:3].lower() == "bot":
        token = token[3:].strip().strip("'\"`")
    return token


def sanitize_chat_id(raw: str) -> str:
    """Strip whitespace and wrapping quotes - kept as a string (not parsed as
    a number) since group chat IDs start with -100."""
    return (raw or "").strip().strip("'\"`")


def _describe_http_status(status_code: int, context: str) -> str:
    if status_code == 404:
        return "invalid or malformed bot token"
    if status_code == 401:
        return "bot token was rejected (wrong or revoked)"
    if status_code == 400 and context == "sendMessage":
        return "likely wrong chat ID, or the bot hasn't been started/added to that chat yet"
    return f"unexpected response from Telegram (HTTP {status_code})"


def get_me(bot_token: str) -> tuple[bool, str]:
    """Verify the bot token itself via the getMe endpoint, before trying to send anything."""
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    try:
        resp = httpx.get(url, timeout=TELEGRAM_TIMEOUT_SECONDS)
    except httpx.RequestError as exc:
        return False, f"Cannot reach Telegram API: {exc}"

    if resp.status_code == 200 and resp.json().get("ok"):
        return True, "Bot token is valid"
    return False, (
        f"getMe failed: HTTP {resp.status_code} "
        f"({_describe_http_status(resp.status_code, 'getMe')})"
    )


def send_message(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if not is_configured(bot_token, chat_id):
        return False, "Telegram bot token or chat ID not configured"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = httpx.post(
            url,
            data={"chat_id": chat_id, "text": text},
            timeout=TELEGRAM_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as exc:
        return False, f"Cannot reach Telegram API: {exc}"

    if resp.status_code == 200 and resp.json().get("ok"):
        return True, "Telegram message sent"
    return False, (
        f"sendMessage failed: HTTP {resp.status_code} "
        f"({_describe_http_status(resp.status_code, 'sendMessage')})"
    )


def test_connection(bot_token: str, chat_id: str) -> dict:
    """Verify the token with getMe first, then actually send a test message."""
    bot_token = sanitize_bot_token(bot_token)
    chat_id = sanitize_chat_id(chat_id)

    if not is_configured(bot_token, chat_id):
        return {
            "ok": False,
            "step": "config",
            "message": "Telegram bot token or chat ID not configured",
        }

    ok, message = get_me(bot_token)
    if not ok:
        return {"ok": False, "step": "getMe", "message": message}

    sent_ok, sent_message = send_message(bot_token, chat_id, "Muninn: testovacia sprava OK")
    return {"ok": sent_ok, "step": "sendMessage", "message": sent_message}
