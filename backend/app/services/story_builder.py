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
from app.models.story import Story

logger = logging.getLogger(__name__)

STORY_GAP_MINUTES = 120   # new story begins after this gap of inactivity


def get_stories(db: Session, limit: int = 200) -> list[Story]:
    """
    Fetch the most recent *limit* stories ordered by start_time.
    """
    return (
        db.query(Story)
        .order_by(Story.start_time.desc())
        .limit(limit)
        .all()
    )


def rebuild_all_stories(db: Session):
    """
    Rebuilds all stories from scratch based on temporal proximity.
    Called on ingest or nightly.
    """
    logger.info("rebuild_all_stories: starting rebuild")
    # Clear existing stories
    db.query(Story).delete()
    db.commit()

    memories = (
        db.query(Memory)
        .filter(Memory.captured_at.isnot(None))
        .order_by(Memory.captured_at.asc())
        .all()
    )

    if not memories:
        return

    stories: list[Story] = []
    current_story: Optional[Story] = None
    gap = timedelta(minutes=STORY_GAP_MINUTES)
    
    idx = 1

    for mem in memories:
        ts = mem.captured_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        if current_story is None or (ts - current_story.end_time) > gap:
            # Save previous story
            if current_story:
                current_story.title = _generate_story_title(db, current_story.memories, idx - 1)
                db.add(current_story)
                
            # Start a new story
            current_story = Story(
                title=f"Story {idx}",
                start_time=ts,
                end_time=ts,
            )
            idx += 1
            stories.append(current_story)

        # Add memory to current story
        if current_story:
            current_story.memories.append(mem)
            current_story.end_time = ts

    # Save the last story
    if current_story:
        current_story.title = _generate_story_title(db, current_story.memories, idx - 1)
        db.add(current_story)

    db.commit()
    logger.info("rebuild_all_stories: rebuilt %d stories", len(stories))


def _generate_story_title(db: Session, memories: list[Memory], idx: int) -> str:
    """Generate a descriptive title for a session based on most common entities and apps."""
    from collections import Counter
    from app.models.entity import Entity
    
    if not memories:
        return f"Story {idx}"

    apps = []
    for m in memories:
        if m.app_detected and m.app_detected.lower() not in ("unknown", ""):
            apps.append(m.app_detected)
    
    app_counter = Counter(apps)
    top_apps = [app for app, _ in app_counter.most_common(2)]
    
    # Try to find top technology or project entities
    entity_names = []
    for m in memories:
        ents = db.query(Entity).filter(Entity.memory_id == m.id).all()
        for e in ents:
            if e.entity_type.value in ("technology", "framework", "project"):
                entity_names.append(e.name)
    
    ent_counter = Counter(entity_names)
    top_ents = [ent for ent, _ in ent_counter.most_common(2)]

    if top_ents:
        title = f"Session: {' & '.join(top_ents)}"
        if top_apps:
            title += f" in {' & '.join(top_apps)}"
        return title
        
    if top_apps:
        return f"Session with {' & '.join(top_apps)}"

    ts = memories[0].captured_at
    if ts:
        return f"Session {idx} — {ts.strftime('%b %d, %H:%M')}"
    return f"Story {idx}"
