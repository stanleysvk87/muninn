from pathlib import Path

from fastapi import APIRouter, HTTPException

from ... import crypto
from ...ai_engine import get_provider
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
    }
