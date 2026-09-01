"""
GET /api/v1/insights — Real aggregate stats for the Insights dashboard.
All figures are computed from actual DB rows — no hardcoded numbers.
"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.memory import Memory
from app.models.entity import Entity
from app.models.screenshot import Screenshot, ScreenshotStatus

router = APIRouter()


@router.get(
    "/insights",
    summary="Aggregate stats for the Insights dashboard",
    description="Returns real memory counts, entity counts, OCR confidence, top tags, top entities, and app breakdown.",
)
def get_insights(db: Session = Depends(get_db)) -> Dict[str, Any]:
    memories = db.query(Memory).all()
    total_memories = len(memories)

    total_entities = db.query(Entity).count()

    # Recent activity — last 7 days
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent_activity_count = sum(
        1 for m in memories
        if m.created_at and m.created_at.replace(tzinfo=None) >= cutoff
    )

    # Average OCR confidence (only where confidence_score was set)
    confidence_scores = [m.confidence_score for m in memories if m.confidence_score is not None]
    avg_confidence = round(sum(confidence_scores) / len(confidence_scores), 4) if confidence_scores else None

    # Pipeline success rate
    total_screenshots = db.query(Screenshot).count()
    completed_screenshots = db.query(Screenshot).filter(Screenshot.status == ScreenshotStatus.COMPLETED).count()
    failed_screenshots = db.query(Screenshot).filter(Screenshot.status == ScreenshotStatus.FAILED).count()
    processing_success_rate = round(completed_screenshots / total_screenshots, 4) if total_screenshots > 0 else None

    # Top tags
    all_tags: List[str] = []
    for m in memories:
        if m.tags and isinstance(m.tags, list):
            all_tags.extend(m.tags)
    tag_counts = Counter(all_tags).most_common(10)
    top_tags = [{"name": name, "count": count} for name, count in tag_counts]

    # Top entities
    all_entities = db.query(Entity).all()
    entity_name_counts = Counter(e.name for e in all_entities).most_common(10)
    top_entities = [{"name": name, "count": count} for name, count in entity_name_counts]

    # App/content-type breakdown
    content_type_counts = Counter(m.content_type for m in memories if m.content_type)
    app_breakdown = [{"name": ct, "count": c} for ct, c in content_type_counts.most_common()]

    today = datetime.utcnow().date()
    activity_by_day: List[Dict[str, Any]] = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = 0
        for m in memories:
            ts = m.captured_at or m.created_at
            if ts and ts.replace(tzinfo=None).date() == day:
                count += 1
        activity_by_day.append({"date": day.isoformat(), "count": count})

    return {
        "total_memories": total_memories,
        "total_entities": total_entities,
        "total_screenshots": total_screenshots,
        "recent_activity_count": recent_activity_count,
        "avg_confidence": avg_confidence,
        "processing_success_rate": processing_success_rate,
        "completed_screenshots": completed_screenshots,
        "failed_screenshots": failed_screenshots,
        "top_tags": top_tags,
        "top_entities": top_entities,
        "app_breakdown": app_breakdown,
        "activity_by_day": activity_by_day,
    }
