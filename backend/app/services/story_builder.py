"""
Phase D -- Story Builder
========================
Groups temporally-close Memories into ``Story`` objects.

A Story represents a coherent work session: screenshots captured within
a sliding time window that share at least one entity or tag.

Stories are computed on-the-fly (not persisted) and returned by the
/api/v1/connections endpoint to the frontend graph visualizer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.memory import Memory

logger = logging.getLogger(__name__)

STORY_GAP_MINUTES = 30   # new story begins after this gap of inactivity


@dataclass
class Story:
    id: str
    title: str
    memory_ids: list[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)


def build_stories(db: Session, limit: int = 200) -> list[Story]:
    """
    Fetch the most recent *limit* memories ordered by captured_at and
    group them into Story objects using a sliding time-window.

    Returns a list of Story dataclasses sorted newest-first.
    """
    memories = (
        db.query(Memory)
        .filter(Memory.captured_at.isnot(None))
        .order_by(Memory.captured_at.asc())
        .limit(limit)
        .all()
    )

    if not memories:
        return []

    stories: list[Story] = []
    current_story: Optional[Story] = None
    gap = timedelta(minutes=STORY_GAP_MINUTES)

    for mem in memories:
        ts = mem.captured_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        if current_story is None or (ts - current_story.end_time) > gap:
            # Start a new story
            story_id = f"story_{len(stories)}"
            current_story = Story(
                id=story_id,
                title=_story_title(mem, len(stories) + 1),
                start_time=ts,
                end_time=ts,
            )
            stories.append(current_story)

        # Add memory to current story
        current_story.memory_ids.append(str(mem.id))
        current_story.end_time = ts
        for tag in (mem.tags or []):
            if tag not in current_story.tags:
                current_story.tags.append(tag)

        # Update title with a richer app context as we accumulate
        if mem.app_detected and mem.app_detected.lower() != "unknown":
            if mem.app_detected not in current_story.title:
                current_story.title = _story_title(mem, stories.index(current_story) + 1)

    stories.reverse()  # newest first
    logger.info("build_stories: grouped %d memories into %d stories", len(memories), len(stories))
    return stories


def _story_title(mem: Memory, idx: int) -> str:
    """Generate a short, descriptive story title from the anchor memory."""
    if mem.app_detected and mem.app_detected.lower() not in ("unknown", ""):
        return f"Session with {mem.app_detected}"
    if mem.title:
        return mem.title[:60]
    ts = mem.captured_at
    if ts:
        return f"Session {idx} — {ts.strftime('%b %d, %H:%M')}"
    return f"Story {idx}"
