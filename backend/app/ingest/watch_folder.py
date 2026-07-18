import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..settings_store import get_setting
from . import pipeline

_observers: dict[str, Observer] = {}
_lock = threading.Lock()


class _Handler(FileSystemEventHandler):
    def on_closed(self, event):
        if not event.is_directory:
            self._spawn(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            self._spawn(Path(event.dest_path))

    def _spawn(self, path: Path) -> None:
        threading.Thread(target=self._handle, args=(path,), daemon=True).start()

    def _handle(self, path: Path) -> None:
        # let the writer (e.g. a Syncthing sync) finish before we touch the file
        time.sleep(2)
        if path.is_file():
            pipeline.process(path, source="watch_folder", source_detail=str(path.parent))


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
            observer = Observer()
            observer.schedule(_Handler(), path, recursive=False)
            observer.start()
            _observers[path] = observer


def stop_all() -> None:
    with _lock:
        for observer in _observers.values():
            observer.stop()
        _observers.clear()
