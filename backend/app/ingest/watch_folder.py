import logging
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..settings_store import get_setting
from . import pipeline

logger = logging.getLogger("muninn.watch_folder")

_observers: dict[str, Observer] = {}
_lock = threading.Lock()


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
    threading.Thread(target=_process_file, args=(path,), daemon=True).start()


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
