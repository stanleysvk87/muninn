import json
from datetime import datetime, timezone
from typing import Any

from .db import execute


def get_setting(key: str, default: Any = None) -> Any:
    row = execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    return json.loads(row["value"])


def set_setting(key: str, value: Any) -> None:
    now = datetime.now(timezone.utc).isoformat()
    execute(
        """INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
        (key, json.dumps(value), now),
    )
