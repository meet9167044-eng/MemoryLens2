"""
Phase E -- Watch Controller API
=================================
Endpoints to start/stop the folder watcher daemon and check its status.

Routes:
    GET  /api/v1/watch         -- watcher status
    POST /api/v1/watch/start   -- start watching a directory
    POST /api/v1/watch/stop    -- stop the watcher
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from app.services.folder_watcher import folder_watcher

router = APIRouter(prefix="/api/v1/watch", tags=["watch"])


# ── Request / Response schemas ───────────────────────────────────────────────

class WatchStartRequest(BaseModel):
    path: str = Field(..., description="Absolute or relative path to the folder to watch")
    recursive: bool = Field(False, description="Watch subdirectories recursively")


class WatchStatusResponse(BaseModel):
    running: bool
    watch_path: Optional[str]
    message: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=WatchStatusResponse, summary="Folder watcher status")
def get_watch_status() -> WatchStatusResponse:
    """Return whether the folder watcher is currently running and which path it monitors."""
    if folder_watcher.is_running:
        return WatchStatusResponse(
            running=True,
            watch_path=folder_watcher.watch_path,
            message=f"Watching: {folder_watcher.watch_path}",
        )
    return WatchStatusResponse(running=False, watch_path=None, message="Watcher is not running.")


@router.post("/start", response_model=WatchStatusResponse, summary="Start folder watcher")
def start_watch(body: WatchStartRequest) -> WatchStatusResponse:
    """
    Start watching a folder for new screenshots.
    Any image file dropped into the folder will be automatically ingested.
    """
    try:
        folder_watcher.start(body.path, recursive=body.recursive)
        return WatchStatusResponse(
            running=True,
            watch_path=folder_watcher.watch_path,
            message=f"Now watching: {folder_watcher.watch_path}",
        )
    except RuntimeError as exc:
        # Already running
        return WatchStatusResponse(
            running=True,
            watch_path=folder_watcher.watch_path,
            message=str(exc),
        )
    except Exception as exc:
        return WatchStatusResponse(
            running=False,
            watch_path=None,
            message=f"Failed to start watcher: {exc}",
        )


@router.post("/stop", response_model=WatchStatusResponse, summary="Stop folder watcher")
def stop_watch() -> WatchStatusResponse:
    """Stop the active folder watcher."""
    folder_watcher.stop()
    return WatchStatusResponse(running=False, watch_path=None, message="Watcher stopped.")
