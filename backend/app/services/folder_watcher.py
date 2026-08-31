"""
Phase E -- Folder Watcher
==========================
Daemon service that monitors a directory for new screenshot files and
automatically ingests them into MemoryLens.

Uses the ``watchdog`` library to receive OS-level filesystem events,
avoiding expensive polling.

Usage (via watch.py API):
    watcher = FolderWatcher()
    watcher.start("/path/to/screenshots")
    watcher.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

WATCHED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class _ScreenshotEventHandler:
    """watchdog event handler that queues new image files for ingestion."""

    def __init__(self, on_new_file):
        self._on_new_file = on_new_file
        self._seen: set[str] = set()

    # watchdog calls dispatch() for every event — we only care about created files
    def dispatch(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() in WATCHED_EXTENSIONS:
            key = str(path)
            if key not in self._seen:
                self._seen.add(key)
                logger.info("FolderWatcher: detected new file %s", path)
                try:
                    self._on_new_file(str(path))
                except Exception as exc:
                    logger.error("FolderWatcher: ingestion error for %s: %s", path, exc)


class FolderWatcher:
    """
    Watches a directory for new screenshots and ingests them automatically.

    Thread-safe singleton pattern -- only one watcher can run at a time.
    """

    def __init__(self):
        self._observer: Optional[object] = None
        self._lock = threading.Lock()
        self._watch_path: Optional[str] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def watch_path(self) -> Optional[str]:
        return self._watch_path

    def start(self, path: str, recursive: bool = False) -> None:
        """
        Start watching *path* for new image files.
        Raises RuntimeError if already running.
        """
        with self._lock:
            if self._running:
                raise RuntimeError(f"FolderWatcher already running on {self._watch_path!r}")

            watch_dir = Path(path)
            if not watch_dir.exists():
                watch_dir.mkdir(parents=True, exist_ok=True)
            if not watch_dir.is_dir():
                raise ValueError(f"Path is not a directory: {path}")

            try:
                from watchdog.observers import Observer
                from watchdog.events import FileSystemEventHandler
            except ImportError:
                raise RuntimeError("watchdog is not installed. Run: pip install watchdog")

            handler = _ScreenshotEventHandler(self._ingest_file)

            class _WatchdogAdapter(FileSystemEventHandler):
                def __init__(self, inner):
                    self._inner = inner
                def on_created(self, event):
                    self._inner.dispatch(event)
                def on_moved(self, event):
                    # treat a move-into-folder as a create
                    self._inner.dispatch(event)

            observer = Observer()
            observer.schedule(_WatchdogAdapter(handler), str(watch_dir), recursive=recursive)
            observer.start()

            self._observer = observer
            self._watch_path = str(watch_dir)
            self._running = True
            logger.info("FolderWatcher: started watching %s (recursive=%s)", path, recursive)

    def stop(self) -> None:
        """Stop the watcher."""
        with self._lock:
            if not self._running or self._observer is None:
                return
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            self._watch_path = None
            self._running = False
            logger.info("FolderWatcher: stopped")

    def _ingest_file(self, file_path: str) -> None:
        """
        Ingest a single file by reading it and calling the ingest pipeline.
        Runs in the watchdog observer thread.
        """
        import io
        import threading as _threading
        from pathlib import Path as _Path

        path = _Path(file_path)

        # Small delay to let the OS finish writing the file
        time.sleep(0.5)

        try:
            data = path.read_bytes()
        except Exception as exc:
            logger.error("FolderWatcher: could not read %s: %s", file_path, exc)
            return

        # Import here to avoid circular imports at module level
        from app.db.session import SessionLocal
        from app.models.screenshot import Screenshot, ScreenshotStatus
        from app.services.storage import storage
        from app.jobs.pipeline import run_pipeline

        db = SessionLocal()
        try:
            # Deduplication check
            file_hash = storage.compute_hash(data)
            existing = db.query(Screenshot).filter(Screenshot.file_hash == file_hash).first()
            if existing:
                logger.info("FolderWatcher: skipping duplicate %s (hash=%s)", path.name, file_hash[:12])
                return

            # Save to storage
            meta = storage.save(data, path.name)

            # Create DB record
            screenshot = Screenshot(
                file_path=meta["file_path"],
                original_filename=path.name,
                file_size_bytes=meta["file_size_bytes"],
                file_hash=meta["file_hash"],
                mime_type=f"image/{path.suffix.lstrip('.').lower()}",
                status=ScreenshotStatus.PENDING,
            )
            db.add(screenshot)
            db.commit()
            db.refresh(screenshot)
            screenshot_id = screenshot.id
        except Exception as exc:
            logger.error("FolderWatcher: DB error for %s: %s", file_path, exc)
            db.rollback()
            return
        finally:
            db.close()

        # Fire pipeline in background thread
        _threading.Thread(
            target=run_pipeline,
            args=(screenshot_id,),
            daemon=True,
            name=f"fw-pipeline-{screenshot_id}",
        ).start()
        logger.info("FolderWatcher: ingested %s -> screenshot_id=%s", path.name, screenshot_id)


# Singleton instance used by the watch API
folder_watcher = FolderWatcher()
