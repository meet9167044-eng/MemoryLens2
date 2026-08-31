"""
Phase F -- Pipeline Queue
==========================
In-process async job queue that replaces raw daemon threads with a
controlled, bounded worker pool.

Design:
    - Uses a threading.Queue (not asyncio) so it works in the sync FastAPI
      context without requiring an event loop change.
    - Fixed worker pool (default: 4 workers) started at app startup.
    - Jobs are tuples of (screenshot_id, priority) -- lower priority value = runs first.
    - Provides status inspection, queue depth, and graceful shutdown.
    - Falls back gracefully: if the queue is full it logs and drops the job
      (the caller should handle retries if needed).

Usage:
    from app.jobs.queue import pipeline_queue
    pipeline_queue.enqueue(screenshot_id)
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
DEFAULT_WORKERS = 4
MAX_QUEUE_SIZE = 500   # prevent unbounded memory growth


class PipelineQueue:
    """
    Thread-pool-backed job queue for screenshot pipeline processing.

    Each submitted screenshot_id is processed by exactly one worker.
    Workers are daemon threads -- they stop automatically when the main
    process exits.
    """

    def __init__(self, num_workers: int = DEFAULT_WORKERS, max_size: int = MAX_QUEUE_SIZE):
        self._q: queue.PriorityQueue = queue.PriorityQueue(maxsize=max_size)
        self._num_workers = num_workers
        self._workers: list[threading.Thread] = []
        self._shutdown_event = threading.Event()
        self._active_count = 0
        self._active_lock = threading.Lock()
        self._processed_total = 0
        self._failed_total = 0
        self._started = False

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Spin up worker threads. Safe to call multiple times (idempotent)."""
        if self._started:
            return
        self._started = True
        for i in range(self._num_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"pipeline-worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)
        logger.info("PipelineQueue: started %d workers (max_queue=%d)", self._num_workers, MAX_QUEUE_SIZE)

    def stop(self, timeout: float = 10.0) -> None:
        """Signal workers to stop and wait for in-flight jobs to complete."""
        self._shutdown_event.set()
        # Poison pills -- one per worker
        for _ in self._workers:
            try:
                self._q.put_nowait((float("inf"), None))
            except queue.Full:
                pass
        for t in self._workers:
            t.join(timeout=timeout)
        logger.info("PipelineQueue: stopped")

    # ── Public API ───────────────────────────────────────────────────────────

    def enqueue(self, screenshot_id: UUID, priority: int = 5) -> bool:
        """
        Add a screenshot_id to the queue for processing.

        priority: lower number = processed first (0=urgent, 5=normal, 10=low)
        Returns True if accepted, False if the queue is full.
        """
        try:
            self._q.put_nowait((priority, str(screenshot_id)))
            logger.debug("PipelineQueue: enqueued screenshot_id=%s (priority=%d, depth=%d)",
                         screenshot_id, priority, self._q.qsize())
            return True
        except queue.Full:
            logger.warning(
                "PipelineQueue: queue full (%d items), dropping screenshot_id=%s",
                MAX_QUEUE_SIZE, screenshot_id,
            )
            return False

    @property
    def depth(self) -> int:
        """Number of jobs waiting in the queue (not counting active jobs)."""
        return self._q.qsize()

    @property
    def active_count(self) -> int:
        """Number of jobs currently being processed by a worker."""
        return self._active_count

    @property
    def stats(self) -> dict:
        return {
            "workers": self._num_workers,
            "queue_depth": self.depth,
            "active_jobs": self.active_count,
            "processed_total": self._processed_total,
            "failed_total": self._failed_total,
            "max_queue_size": MAX_QUEUE_SIZE,
        }

    # ── Worker loop ──────────────────────────────────────────────────────────

    def _worker_loop(self) -> None:
        """Main loop for each worker thread."""
        from app.jobs.pipeline import run_pipeline

        while not self._shutdown_event.is_set():
            try:
                priority, sid = self._q.get(timeout=1.0)
            except queue.Empty:
                continue

            if sid is None:  # poison pill
                self._q.task_done()
                break

            with self._active_lock:
                self._active_count += 1

            try:
                logger.info("PipelineQueue: processing screenshot_id=%s", sid)
                run_pipeline(screenshot_id=sid)
                with self._active_lock:
                    self._processed_total += 1
            except Exception as exc:
                logger.error(
                    "PipelineQueue: unhandled error for screenshot_id=%s: %s",
                    sid, exc, exc_info=True,
                )
                with self._active_lock:
                    self._failed_total += 1
            finally:
                with self._active_lock:
                    self._active_count -= 1
                self._q.task_done()


# ── Singleton ────────────────────────────────────────────────────────────────
pipeline_queue = PipelineQueue()
