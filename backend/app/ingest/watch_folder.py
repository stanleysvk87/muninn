import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..settings_store import get_setting
from . import pipeline

logger = logging.getLogger("muninn.watch_folder")

_observers: dict[str, Observer] = {}
_lock = threading.Lock()

# Each ingest holds an AI CLI subprocess open for up to 120s per provider and
# hits the single shared SQLite connection. This used to be one raw
# threading.Thread per file with no pool and no bound, and _scan_existing()
# calls it in a loop -- registering a folder with 2000 files in it launched
# 2000 threads and 2000 claude/codex subprocesses at once on an RK3588.
# Two workers keep the queue draining without swamping the board; extra work
# waits in the executor's queue instead of in the process table.
MAX_CONCURRENT_INGESTS = 2
_executor = ThreadPoolExecutor(
    max_workers=MAX_CONCURRENT_INGESTS, thread_name_prefix="muninn-watch"
)
# Files handed to the pool but not finished yet -- a watchdog on_closed plus
# an on_moved for the same path (or a re-scan of a folder whose queue hasn't
# drained) must not queue the same document twice.
_inflight: set[str] = set()
_inflight_lock = threading.Lock()


def _process_file(path: Path) -> None:
    # let the writer (e.g. a Syncthing sync) finish before we touch the file
    time.sleep(2)
    if not path.is_file():
        return
    try:
        pipeline.process(path, source="watch_folder", source_detail=str(path.parent))
    except Exception:
        logger.exception("Watch folder: spracovanie %s zlyhalo", path)


def _spawn(path: Path) -> None:
    key = str(path)
    with _inflight_lock:
        if key in _inflight:
            return
        _inflight.add(key)

    def _run() -> None:
        try:
            _process_file(path)
        finally:
            with _inflight_lock:
                _inflight.discard(key)

    try:
        _executor.submit(_run)
    except RuntimeError:
        # Executor already shut down (app is stopping).
        with _inflight_lock:
            _inflight.discard(key)


class _Handler(FileSystemEventHandler):
    def on_closed(self, event):
        if not event.is_directory:
            _spawn(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            _spawn(Path(event.dest_path))


def _scan_existing(directory: Path) -> None:
    """inotify (via watchdog) only reports events from the moment the observer
    attaches -- a file that landed in the folder while the app was down, or in
    the brief window before the observer starts, would otherwise sit there
    forever, invisible. Sweep once whenever a folder is (re)registered so
    nothing dropped during a restart gets silently missed (seen in production
    during a redeploy)."""
    for entry in directory.iterdir():
        if entry.is_file():
            _spawn(entry)


def sync_watch_folders() -> None:
    """(Re)apply the configured watch folders. Safe to call repeatedly — starts
    observers for newly added folders and stops them for removed ones, so a
    Settings UI change takes effect without a process restart."""
    folders = get_setting("watch_folders", [])
    with _lock:
        for path in list(_observers):
            if path not in folders:
                _observers.pop(path).stop()

        for path in folders:
            if path in _observers:
                continue
            directory = Path(path)
            if not directory.is_dir():
                continue
            _scan_existing(directory)
            observer = Observer()
            observer.schedule(_Handler(), path, recursive=False)
            observer.start()
            _observers[path] = observer


def stop_all() -> None:
    with _lock:
        for observer in _observers.values():
            observer.stop()
        _observers.clear()
    # Drop anything still queued -- on shutdown there is no point starting
    # new AI subprocesses that will be killed seconds later anyway.
    _executor.shutdown(wait=False, cancel_futures=True)
