"""In-process login throttling.

/api/auth/login and /api/auth/bootstrap are the only unauthenticated
state-changing endpoints in the app, and login runs PBKDF2-HMAC-SHA256 with
200 000 iterations -- measured at ~0.11 s per attempt on the RK3588 this
runs on. With no attempt limit that is two problems at once: an offline-speed
online guessing oracle, and a CPU amplifier where a few dozen concurrent
requests saturate every core and starve the rest of the service.

Deliberately in-process (a dict + a lock), not in SQLite: this is a
single-process deployment (see docs/adr/0002-single-process-no-reverse-proxy)
and the counters are cheap, short-lived and safe to lose on restart. It
does mean a restart clears the lockout -- an attacker cannot trigger that,
only the owner can.
"""

import threading
import time

WINDOW_SECONDS = 15 * 60
MAX_FAILURES = 8
LOCKOUT_SECONDS = 15 * 60

_failures: dict[str, list[float]] = {}
_lock = threading.Lock()


def _prune(key: str, now: float) -> list[float]:
    stamps = [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS]
    if stamps:
        _failures[key] = stamps
    else:
        _failures.pop(key, None)
    return stamps


def retry_after(keys: list[str]) -> int | None:
    """Seconds the caller must wait, or None if it may try now."""
    now = time.monotonic()
    with _lock:
        worst = None
        for key in keys:
            stamps = _prune(key, now)
            if len(stamps) >= MAX_FAILURES:
                remaining = int(LOCKOUT_SECONDS - (now - stamps[-1])) + 1
                worst = max(worst or 0, max(remaining, 1))
        return worst


def record_failure(keys: list[str]) -> None:
    now = time.monotonic()
    with _lock:
        for key in keys:
            stamps = _prune(key, now)
            stamps.append(now)
            _failures[key] = stamps


def reset(keys: list[str]) -> None:
    with _lock:
        for key in keys:
            _failures.pop(key, None)


def clear_all() -> None:
    """Test helper -- the counters are process-global."""
    with _lock:
        _failures.clear()
