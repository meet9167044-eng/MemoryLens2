"""
Phase D - Knowledge Graph Relationship Engine
----------------------------------------------
Compares a Memory to all existing Memories and generates
Relationship records based on:
  1. Shared entities  (same entity name, case-insensitive)
  2. Shared tags      (overlap in memory.tags JSON array)
  3. Semantic similarity (real cosine similarity via pgvector)
  4. Temporal proximity (captured_at within short time window)
  5. Domain linking    (same website/domain detected)

Design rules (from spec):
  - source_id is always the lexicographically SMALLER UUID so the
    (source_id, target_id, rel_type) unique constraint prevents
    duplicate undirected rows.
  - Score is a float 0.0–1.0.
"""

from __future__ import annotations

import logging
import math
from datetime import timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.entity import Entity
from app.models.relationship import Relationship, RelationshipType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _ordered_ids(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    """Return (smaller_uuid, larger_uuid) so pairs are always canonical."""
    return (a, b) if str(a) < str(b) else (b, a)


def _upsert_relationship(
    db: Session,
    source_id: UUID,
    target_id: UUID,
    rel_type: RelationshipType,
    score: float,
    explanation: str,
) -> Relationship:
    """
    Insert or update a Relationship row.
    Returns the Relationship object (not yet committed – caller commits).
    """
    src, tgt = _ordered_ids(source_id, target_id)

    existing = (
        db.query(Relationship)
        .filter_by(source_id=src, target_id=tgt, rel_type=rel_type)
        .first()
    )
    if existing:
        # Update if the new score is higher
        if score > existing.score:
            existing.score = score
            existing.explanation = explanation
        return existing

    rel = Relationship(
        source_id=src,
        target_id=tgt,
        rel_type=rel_type,
        score=score,
        explanation=explanation,
    )
    db.add(rel)
    return rel


# ─────────────────────────────────────────────
# Scoring functions
# ─────────────────────────────────────────────

def _score_shared_entities(
    memory_a: Memory,
    memory_b: Memory,
    entities_a: list[Entity],
    entities_b: list[Entity],
) -> tuple[float, str]:
    """
    Score based on number of shared entity names (case-insensitive).
    Score = shared / max(total_unique_a, total_unique_b), capped at 1.0
    """
    names_a = {e.name.lower() for e in entities_a}
    names_b = {e.name.lower() for e in entities_b}
    shared  = names_a & names_b

    if not shared:
        return 0.0, ""

    denom = max(len(names_a), len(names_b), 1)
    score = min(len(shared) / denom, 1.0)
    explanation = f"Shared entities: {', '.join(sorted(shared)[:5])}"
    return round(score, 4), explanation


def _score_shared_tags(
    memory_a: Memory,
    memory_b: Memory,
) -> tuple[float, str]:
    """
    Jaccard similarity over the tags arrays stored in memory.tags (JSONB list).
    """
    tags_a = set(memory_a.tags or [])
    tags_b = set(memory_b.tags or [])
    union  = tags_a | tags_b

    if not union:
        return 0.0, ""

    shared  = tags_a & tags_b
    if not shared:
        return 0.0, ""

    score = round(len(shared) / len(union), 4)
    explanation = f"Shared tags: {', '.join(sorted(shared)[:5])}"
    return score, explanation


def _score_semantic(
    memory_a: Memory,
    memory_b: Memory,
) -> tuple[float, str]:
    """
    Phase D: Real semantic similarity using stored pgvector embeddings.
    Uses cosine similarity: score = 1 - cosine_distance.
    Only runs when both memories have an embedding vector stored.
    """
    vec_a = memory_a.embedding
    vec_b = memory_b.embedding

    if vec_a is None or vec_b is None:
        return 0.0, ""

    # Compute cosine similarity manually from stored vectors
    try:
        a = list(vec_a)
        b = list(vec_b)
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0, ""
        score = dot / (mag_a * mag_b)
        score = round(max(0.0, min(1.0, score)), 4)
        if score >= 0.65:
            return score, f"Semantic similarity: {score:.2%}"
    except Exception as exc:
        logger.debug("Semantic scoring error: %s", exc)

    return 0.0, ""


def _score_temporal(
    memory_a: Memory,
    memory_b: Memory,
    window_hours: float = 2.0,
) -> tuple[float, str]:
    """
    Phase D: Score based on how close two screenshots were captured in time.
    Full score (1.0) if within 5 minutes, decays linearly to 0 at window_hours.
    Only runs when both memories have a captured_at timestamp.
    """
    ts_a = memory_a.captured_at
    ts_b = memory_b.captured_at
    if ts_a is None or ts_b is None:
        return 0.0, ""

    # Ensure both are timezone-aware for subtraction
    if ts_a.tzinfo is None:
        ts_a = ts_a.replace(tzinfo=timezone.utc)
    if ts_b.tzinfo is None:
        ts_b = ts_b.replace(tzinfo=timezone.utc)

    diff_seconds = abs((ts_a - ts_b).total_seconds())
    window_seconds = window_hours * 3600

    if diff_seconds >= window_seconds:
        return 0.0, ""

    score = round(1.0 - (diff_seconds / window_seconds), 4)
    if score < 0.1:
        return 0.0, ""

    diff_min = diff_seconds / 60
    explanation = f"Captured {diff_min:.0f} min apart"
    return score, explanation


def _score_domain(
    memory_a: Memory,
    memory_b: Memory,
) -> tuple[float, str]:
    """
    Phase D: Score based on shared domain (website) detected.
    Perfect score when both were captured on the same domain.
    """
    domain_a = (memory_a.domain or "").strip().lower()
    domain_b = (memory_b.domain or "").strip().lower()

    if not domain_a or not domain_b or domain_a == "unknown":
        return 0.0, ""

    if domain_a == domain_b:
        return 0.85, f"Same domain: {domain_a}"

    return 0.0, ""


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def compute_relationships_for_memory(
    db: Session,
    memory_id: UUID,
    min_score: float = 0.1,
) -> list[Relationship]:
    """
    Compare *memory_id* against every other Memory in the DB and persist
    any Relationship that scores above *min_score*.

    Returns the list of Relationship objects (committed to the session).
    """
    target_memory: Optional[Memory] = db.get(Memory, memory_id)
    if not target_memory:
        raise ValueError(f"Memory {memory_id} not found")

    target_entities: list[Entity] = (
        db.query(Entity).filter(Entity.memory_id == memory_id).all()
    )

    # Phase F: Optimize candidate selection to avoid O(n²) comparisons
    candidate_ids = set()

    # 1. Temporal candidates (within +/- 2 hours)
    if target_memory.captured_at:
        from datetime import timedelta, timezone
        temp_start = target_memory.captured_at - timedelta(hours=2)
        temp_end = target_memory.captured_at + timedelta(hours=2)
        if temp_start.tzinfo is None:
            temp_start = temp_start.replace(tzinfo=timezone.utc)
            temp_end = temp_end.replace(tzinfo=timezone.utc)
        temporal_candidates = (
            db.query(Memory.id)
            .filter(Memory.id != memory_id)
            .filter(Memory.captured_at.between(temp_start, temp_end))
            .all()
        )
        for row in temporal_candidates:
            candidate_ids.add(row[0])

    # 2. Domain candidates
    domain = (target_memory.domain or "").strip().lower()
    if domain and domain != "unknown":
        domain_candidates = (
            db.query(Memory.id)
            .filter(Memory.id != memory_id)
            .filter(Memory.domain == domain)
            .all()
        )
        for row in domain_candidates:
            candidate_ids.add(row[0])

    # 3. Entity overlap candidates
    if target_entities:
        target_entity_names = [e.name for e in target_entities]
        entity_candidates = (
            db.query(Entity.memory_id)
            .filter(Entity.memory_id != memory_id)
            .filter(Entity.name.in_(target_entity_names))
            .distinct()
            .all()
        )
        for row in entity_candidates:
            candidate_ids.add(row[0])

    # 4. Tag overlap candidates
    if target_memory.tags:
        from sqlalchemy import or_, cast, String
        tag_filters = [Memory.tags.cast(String).ilike(f'%"{t}"%') for t in target_memory.tags]
        tag_candidates = (
            db.query(Memory.id)
            .filter(Memory.id != memory_id)
            .filter(or_(*tag_filters))
            .all()
        )
        for row in tag_candidates:
            candidate_ids.add(row[0])

    # 5. Semantic similarity candidates (pgvector top-K)
    if target_memory.embedding is not None:
        try:
            semantic_candidates = (
                db.query(Memory.id)
                .filter(Memory.id != memory_id)
                .filter(Memory.embedding != None)
                .order_by(Memory.embedding.cosine_distance(target_memory.embedding))
                .limit(50)
                .all()
            )
            for row in semantic_candidates:
                candidate_ids.add(row[0])
        except Exception as exc:
            logger.debug("Could not fetch semantic candidates via pgvector: %s", exc)

    if not candidate_ids:
        logger.info("compute_relationships_for_memory: No candidates found for %s", memory_id)
        return []

    # Load only the candidates
    other_memories: list[Memory] = (
        db.query(Memory).filter(Memory.id.in_(candidate_ids)).all()
    )
    logger.info("compute_relationships_for_memory: Evaluated %d candidates for %s", len(other_memories), memory_id)

    created: list[Relationship] = []

    for other in other_memories:
        other_entities = (
            db.query(Entity).filter(Entity.memory_id == other.id).all()
        )

        # 1. Shared entities
        ent_score, ent_expl = _score_shared_entities(
            target_memory, other, target_entities, other_entities
        )
        if ent_score >= min_score:
            rel = _upsert_relationship(
                db,
                source_id=memory_id,
                target_id=other.id,
                rel_type=RelationshipType.SHARED_ENTITY,
                score=ent_score,
                explanation=ent_expl,
            )
            created.append(rel)

        # 2. Shared tags
        tag_score, tag_expl = _score_shared_tags(target_memory, other)
        if tag_score >= min_score:
            rel = _upsert_relationship(
                db,
                source_id=memory_id,
                target_id=other.id,
                rel_type=RelationshipType.SHARED_TAG,
                score=tag_score,
                explanation=tag_expl,
            )
            created.append(rel)

        # 3. Phase D: Semantic similarity via pgvector embeddings
        sem_score, sem_expl = _score_semantic(target_memory, other)
        if sem_score >= 0.65:
            rel = _upsert_relationship(
                db,
                source_id=memory_id,
                target_id=other.id,
                rel_type=RelationshipType.SEMANTIC,
                score=sem_score,
                explanation=sem_expl,
            )
            created.append(rel)

        # 4. Phase D: Temporal proximity
        temp_score, temp_expl = _score_temporal(target_memory, other)
        if temp_score >= min_score:
            rel = _upsert_relationship(
                db,
                source_id=memory_id,
                target_id=other.id,
                rel_type=RelationshipType.TEMPORAL,
                score=temp_score,
                explanation=temp_expl,
            )
            created.append(rel)

        # 5. Phase D: Domain linking
        dom_score, dom_expl = _score_domain(target_memory, other)
        if dom_score >= min_score:
            rel = _upsert_relationship(
                db,
                source_id=memory_id,
                target_id=other.id,
                rel_type=RelationshipType.DOMAIN,
                score=dom_score,
                explanation=dom_expl,
            )
            created.append(rel)

    db.commit()
    logger.info(
        "compute_relationships_for_memory: memory=%s → %d relationships",
        memory_id, len(created),
    )
    return created


def get_related_memories(
    db: Session,
    memory_id: UUID,
    limit: int = 10,
) -> list[dict]:
    """
    Return the top *limit* related memories for *memory_id*,
    ordered by descending score.

    Returns a list of dicts:
        {memory_id, title, score, rel_type, explanation}
    """
    uid = str(memory_id)

    rows = (
        db.query(Relationship)
        .filter(
            (Relationship.source_id == memory_id) |
            (Relationship.target_id == memory_id)
        )
        .order_by(Relationship.score.desc())
        .limit(limit)
        .all()
    )

    results = []
    for row in rows:
        other_id = row.target_id if str(row.source_id) == uid else row.source_id
        other_memory: Optional[Memory] = db.get(Memory, other_id)
        results.append({
            "memory_id":   str(other_id),
            "title":       other_memory.title if other_memory else None,
            "score":       row.score,
            "rel_type":    row.rel_type,
            "explanation": row.explanation,
            # Enriched — lets the frontend show cards without a second fetch
            "summary":     other_memory.summary if other_memory else None,
            "timestamp":   other_memory.created_at.isoformat() if other_memory and other_memory.created_at else None,
        })

    return results

