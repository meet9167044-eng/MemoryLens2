"""
Phase 9 - Memories API Router
Exposes:
  GET    /api/v1/memories              — list memories
  GET    /api/v1/memories/{id}         — single memory detail
  GET    /api/v1/memories/{id}/related — related memories
  POST   /api/v1/memories/{id}/compute-relationships — trigger relationship engine
  DELETE /api/v1/memories/{id}         — delete memory + image file (Fix 2.1)
"""
from __future__ import annotations
import os as _os

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.session import get_db
from app.models.memory import Memory
from app.models.relationship import Relationship
from app.schemas.relationships import RelatedMemoriesResponse, RelatedMemoryResponse
from app.schemas.memories import (
    MemoryResponse, SourceSchema, ScreenshotSchema, ContentSchema, 
    EntitySchema, RelatedMemorySchema, MetadataSchema
)
from app.processing.relationships import compute_relationships_for_memory, get_related_memories

router = APIRouter(prefix="/memories", tags=["memories"])


def map_memory_to_response(db: Session, memory: Memory) -> MemoryResponse:
    """Map a SQLAlchemy Memory object exactly to the frontend MemoryResponse JSON."""
    
    # 1. Source — Phase B: use real app_detected from LLM extraction
    app_name = memory.app_detected or "Unknown"
    app_type = memory.content_type or "other"
    # Normalise content_type values to frontend-expected enum
    if app_type not in ("desktop", "browser", "terminal", "document", "other"):
        app_type = "other"
        
    # 2. Screenshot
    screenshot_id = str(memory.screenshot_id) if memory.screenshot_id else ""
    image_url = f"/api/v1/screenshots/{screenshot_id}/image"
    
    # 3. Content
    content = ContentSchema(
        ocrText=memory.raw_ocr_text or "",
        title=memory.title or "Untitled Memory",
        summary=memory.summary or ""
    )
    
    # 4. Entities
    entities = []
    for ent in memory.entities:
        frontend_type = "other"
        if ent.entity_type.value in ['technology', 'framework', 'company', 'person', 'project', 'topic', 'tool']:
            frontend_type = ent.entity_type.value
        elif ent.entity_type.value == 'organization':
            frontend_type = 'company'
            
        entities.append(EntitySchema(
            id=str(ent.id),
            name=ent.name,
            type=frontend_type
        ))
        
    # 5. Tags
    tags = memory.tags or []
    
    # 6. Related Memories
    rels = db.query(Relationship).filter(
        or_(Relationship.source_id == memory.id, Relationship.target_id == memory.id)
    ).all()
    
    related = []
    for r in rels:
        other_id = r.target_id if r.source_id == memory.id else r.source_id
        rel_type = "semantic_similarity"
        if r.rel_type.value == "shared_entity":
            rel_type = "entity_overlap"
        elif r.rel_type.value == "shared_tag":
            rel_type = "same_topic"
            
        related.append(RelatedMemorySchema(
            memoryId=str(other_id),
            relationship=rel_type,
            similarityScore=r.score
        ))
        
    # 7. Metadata
    metadata = MetadataSchema(
        language="english",
        contentType=memory.content_type or "unknown",
        confidence=memory.confidence_score or 0.95
    )

    # Phase B: use captured_at (real screenshot time) over created_at (upload time)
    timestamp = (
        memory.captured_at.isoformat()
        if memory.captured_at
        else (memory.created_at.isoformat() if memory.created_at else "")
    )

    return MemoryResponse(
        id=str(memory.id),
        timestamp=timestamp,
        source=SourceSchema(app=app_name, type=app_type),
        screenshot=ScreenshotSchema(id=screenshot_id, imageUrl=image_url),
        content=content,
        entities=entities,
        tags=tags,
        relatedMemories=related,
        metadata=metadata
    )


@router.get("", response_model=list[MemoryResponse])
def list_memories(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List all memories, ordered by captured_at (real screenshot time) desc.
    Falls back to created_at ordering for memories without EXIF data.
    """
    from sqlalchemy import case
    order_col = case(
        (Memory.captured_at.isnot(None), Memory.captured_at),
        else_=Memory.created_at,
    )
    memories = db.query(Memory).order_by(order_col.desc()).offset(skip).limit(limit).all()
    return [map_memory_to_response(db, m) for m in memories]


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory(
    memory_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a single memory by ID.
    """
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
        
    return map_memory_to_response(db, memory)


@router.get("/{memory_id}/related", response_model=RelatedMemoriesResponse)
def related_memories(
    memory_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Return the top *limit* memories most related to *memory_id*.
    Relationships are scored by shared entities, shared tags, and
    (eventually) semantic similarity.
    """
    rows = get_related_memories(db, memory_id=memory_id, limit=limit)
    if rows is None:
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")

    return RelatedMemoriesResponse(
        memory_id=str(memory_id),
        related=[RelatedMemoryResponse(**r) for r in rows],
    )


@router.post("/{memory_id}/compute-relationships", status_code=202)
def trigger_compute_relationships(
    memory_id: UUID,
    min_score: float = Query(default=0.1, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """
    Trigger the relationship engine for *memory_id*.
    Compares this memory against all others and persists relationship rows.
    Returns a summary of how many were created/updated.
    """
    try:
        rels = compute_relationships_for_memory(db, memory_id=memory_id, min_score=min_score)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "memory_id": str(memory_id),
        "relationships_computed": len(rels),
        "status": "ok",
    }


# ── Fix 2.1: Delete memory + screenshot file ────────────────────────────────

@router.delete(
    "/{memory_id}",
    status_code=204,
    summary="Delete a memory and its screenshot image",
    description=(
        "Permanently deletes the Memory record, its Screenshot record, "
        "and the image file from disk. This action is irreversible."
    ),
)
def delete_memory(
    memory_id: UUID,
    db: Session = Depends(get_db),
):
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    # Delete the image file from disk before removing DB records
    screenshot = memory.screenshot
    if screenshot and screenshot.file_path:
        try:
            if _os.path.exists(screenshot.file_path):
                _os.remove(screenshot.file_path)
        except OSError as exc:
            # Log but don't block deletion if file removal fails
            import logging
            logging.getLogger(__name__).warning(
                "Could not remove image file %s: %s", screenshot.file_path, exc
            )

    # Cascading delete handles entities, jobs, relationships via FK constraints
    db.delete(memory)
    db.commit()
    # 204 No Content — return nothing
