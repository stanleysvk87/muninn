import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ... import crypto, telegram
from ...ai_engine import get_provider, get_provider_chain
from ...ai_engine.base import ExtractionError
from ...db import execute
from ...ingest.watch_folder import sync_watch_folders
from ...settings_store import get_setting, set_setting

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/watch-folders")
def list_watch_folders():
    return {"folders": get_setting("watch_folders", [])}


@router.post("/watch-folders")
def add_watch_folder(payload: dict):
    path = payload.get("path", "")
    if not path or not Path(path).is_dir():
        raise HTTPException(status_code=422, detail="Priecinok neexistuje alebo cesta chyba")
    folders = get_setting("watch_folders", [])
    if path not in folders:
        folders.append(path)
        set_setting("watch_folders", folders)
        sync_watch_folders()
    return {"folders": folders}


@router.delete("/watch-folders")
def remove_watch_folder(path: str):
    folders = [f for f in get_setting("watch_folders", []) if f != path]
    set_setting("watch_folders", folders)
    sync_watch_folders()
    return {"folders": folders}


@router.get("/mail")
def get_mail_settings():
    config = dict(get_setting("mail", {}))
    config.pop("password_encrypted", None)
    return config


@router.put("/mail")
def update_mail_settings(payload: dict):
    config = dict(get_setting("mail", {}))
    config.update({k: v for k, v in payload.items() if k != "password"})
    if payload.get("password"):
        config["password_encrypted"] = crypto.encrypt(payload["password"])
    set_setting("mail", config)
    safe = dict(config)
    safe.pop("password_encrypted", None)
    return safe


@router.get("/ai-provider")
def get_ai_provider_settings():
    return {"mode": get_setting("ai_provider_mode", "auto")}


@router.put("/ai-provider")
def update_ai_provider_settings(payload: dict):
    mode = payload.get("mode", "auto")
    set_setting("ai_provider_mode", mode)
    if payload.get("api_key"):
        set_setting("anthropic_api_key_encrypted", crypto.encrypt(payload["api_key"]))
    return {"mode": mode}


@router.post("/ai-provider/test")
def test_ai_provider():
    try:
        provider = get_provider()
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"provider": provider.name, "model": provider.model}


@router.get("/telegram")
def get_telegram_settings():
    config = dict(get_setting("telegram", {}))
    config.pop("bot_token_encrypted", None)
    config.setdefault("enabled", False)
    config.setdefault("chat_id", "")
    config.setdefault("notify_days_before", 30)
    config["configured"] = bool(get_setting("telegram", {}).get("bot_token_encrypted"))
    return config


@router.put("/telegram")
def update_telegram_settings(payload: dict):
    config = dict(get_setting("telegram", {}))
    if "enabled" in payload:
        config["enabled"] = bool(payload["enabled"])
    if "chat_id" in payload:
        config["chat_id"] = telegram.sanitize_chat_id(payload["chat_id"])
    if "notify_days_before" in payload:
        config["notify_days_before"] = int(payload["notify_days_before"])
    if payload.get("bot_token"):
        config["bot_token_encrypted"] = crypto.encrypt(telegram.sanitize_bot_token(payload["bot_token"]))
    set_setting("telegram", config)
    safe = dict(config)
    safe.pop("bot_token_encrypted", None)
    safe["configured"] = bool(config.get("bot_token_encrypted"))
    return safe


@router.post("/telegram/test")
def test_telegram():
    config = get_setting("telegram", {})
    bot_token = crypto.decrypt(config["bot_token_encrypted"]) if config.get("bot_token_encrypted") else ""
    result = telegram.test_connection(bot_token, config.get("chat_id", ""))
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/usage")
def get_usage():
    total = execute(
        """SELECT COUNT(*) AS documents,
                  COALESCE(SUM(cost_usd), 0) AS cost_usd,
                  COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens
           FROM documents WHERE status = 'processed'"""
    ).fetchone()
    by_provider = execute(
        """SELECT ai_provider,
                  COUNT(*) AS documents,
                  COALESCE(SUM(cost_usd), 0) AS cost_usd,
                  COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens
           FROM documents WHERE status = 'processed'
           GROUP BY ai_provider ORDER BY documents DESC"""
    ).fetchall()
    return {
        "total": dict(total),
        "by_provider": [dict(row) for row in by_provider],
        "metering": {
            "api_documents": sum(
                row["documents"]
                for row in by_provider
                if row["ai_provider"] == "anthropic_api"
            ),
            "cli_documents": sum(
                row["documents"]
                for row in by_provider
                if row["ai_provider"] in {"claude_cli", "codex_cli"}
            ),
        },
    }


def _cli_status(binary: str, version_args: list[str] | None = None) -> dict:
    path = shutil.which(binary)
    if not path:
        return {"name": binary, "available": False, "path": None, "version": None}

    version = None
    if version_args:
        try:
            proc = subprocess.run(
                [binary, *version_args],
                capture_output=True,
                text=True,
                timeout=5,
            )
            text = (proc.stdout or proc.stderr).strip()
            version = text.splitlines()[0][:160] if text else None
        except (OSError, subprocess.SubprocessError):
            version = None

    return {"name": binary, "available": True, "path": path, "version": version}


@router.get("/diagnostics")
def get_diagnostics():
    failed_uids = get_setting("mail_failed_uids", {})
    recent_failed = execute(
        """SELECT id, original_filename, source, source_detail, ai_provider,
                  substr(coalesce(error_message, ''), 1, 300) AS error_message,
                  created_at
           FROM documents
           WHERE status = 'failed'
           ORDER BY created_at DESC
           LIMIT 8"""
    ).fetchall()
    provider_counts = execute(
        """SELECT ai_provider, status, COUNT(*) AS documents
           FROM documents
           GROUP BY ai_provider, status
           ORDER BY documents DESC"""
    ).fetchall()
    recent_jobs = execute(
        """SELECT j.*, d.correspondent, d.doc_type
           FROM ingest_jobs j
           LEFT JOIN documents d ON d.id = j.document_id
           ORDER BY j.started_at DESC, j.id DESC
           LIMIT 12"""
    ).fetchall()

    chain = []
    try:
        chain = [{"name": p.name, "model": p.model} for p in get_provider_chain()]
    except ExtractionError:
        chain = []

    return {
        "ai_mode": get_setting("ai_provider_mode", "auto"),
        "provider_chain": chain,
        "cli": {
            "claude": _cli_status("claude", ["--version"]),
            "codex": _cli_status("codex", ["--version"]),
        },
        "anthropic_api_configured": bool(get_setting("anthropic_api_key_encrypted")),
        "mail": {
            "enabled": bool(get_setting("mail", {}).get("enabled")),
            "last_uid": get_setting("mail_last_uid", 0),
            "failed_uids": failed_uids,
            "failed_uid_count": len(failed_uids),
        },
        "documents": {
            "provider_counts": [dict(row) for row in provider_counts],
            "recent_failed": [dict(row) for row in recent_failed],
        },
        "jobs": [dict(row) for row in recent_jobs],
    }
