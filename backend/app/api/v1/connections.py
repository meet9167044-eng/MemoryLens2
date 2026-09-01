"""
GET /api/v1/connections — Phase D: Memory Knowledge Graph

Returns nodes and edges for the Connections screen graph visualizer,
plus stories (temporal session groups) and project clusters.

Nodes: Memory nodes + Entity nodes.
Edges: Relationship rows (shared_entity, shared_tag, semantic, temporal, domain).

If no real memories exist, returns a minimal demo graph derived from
the synthetic dataset so the UI always has something to show.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.memory import Memory
from app.models.entity import Entity
from app.models.relationship import Relationship
from app.services.story_builder import build_stories
from app.services.project_detector import build_project_clusters

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Response shapes (plain dicts — intentionally simple for graph lib flexibility)
# ─────────────────────────────────────────────────────────────────────────────

def _memory_node(m: Memory) -> Dict[str, Any]:
    # Phase B: prefer captured_at (real screenshot time) over created_at (upload time)
    real_ts = m.captured_at or m.created_at
    return {
        "id": f"mem_{m.id}",
        "type": "memory",
        "label": (m.title or "Untitled")[:50],
        "data": {
            "memoryId": str(m.id),
            "timestamp": real_ts.isoformat() if real_ts else "",
            "contentType": m.content_type or "other",
            "app": m.app_detected or "Unknown",
            "domain": m.domain or "",
            "tags": m.tags or [],
        },
    }


def _entity_node(e: Entity) -> Dict[str, Any]:
    return {
        "id": f"ent_{e.id}",
        "type": "entity",
        "label": e.name,
        "data": {
            "entityId": str(e.id),
            "entityType": e.entity_type.value,
        },
    }


def _relationship_edge(rel: Relationship, idx: int) -> Dict[str, Any]:
    return {
        "id": f"edge_{idx}",
        "source": f"mem_{rel.source_id}",
        "target": f"mem_{rel.target_id}",
        "label": rel.rel_type.value.replace("_", " "),
        "data": {
            "score": rel.score,
            "relType": rel.rel_type.value,
            "explanation": rel.explanation or "",
        },
    }


def _entity_memory_edge(m: Memory, e: Entity, idx: int) -> Dict[str, Any]:
    return {
        "id": f"me_edge_{idx}",
        "source": f"mem_{m.id}",
        "target": f"ent_{e.id}",
        "label": "has entity",
        "data": {"score": 1.0, "relType": "has_entity"},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fallback demo graph from synthetic data
# ─────────────────────────────────────────────────────────────────────────────

def _synthetic_demo_graph() -> Dict[str, Any]:
    """Build a demo graph from the synthetic dataset for empty-DB state."""
    from app.data.synthetic_memories import SYNTHETIC_MEMORIES
    nodes: List[Dict] = []
    edges: List[Dict] = []
    seen_entities: Dict[str, int] = {}

    for i, mem in enumerate(SYNTHETIC_MEMORIES[:15]):  # limit for perf
        nodes.append({
            "id": f"mem_{mem['id']}",
            "type": "memory",
            "label": mem.get("content", {}).get("title", "Untitled")[:50],
            "data": {
                "memoryId": mem["id"],
                "timestamp": mem.get("timestamp", ""),
                "contentType": mem.get("source", {}).get("type", "other"),
                "tags": mem.get("tags", []),
            },
        })

        for ent in mem.get("entities", []):
            ent_key = ent["name"].lower()
            if ent_key not in seen_entities:
                seen_entities[ent_key] = len(seen_entities)
                nodes.append({
                    "id": f"ent_{ent_key}",
                    "type": "entity",
                    "label": ent["name"],
                    "data": {"entityType": ent.get("type", "other")},
                })
            edges.append({
                "id": f"me_{i}_{ent_key}",
                "source": f"mem_{mem['id']}",
                "target": f"ent_{ent_key}",
                "label": "has entity",
                "data": {"score": 1.0, "relType": "has_entity"},
            })

        # Tag-based links to nearby memories
        for j, other in enumerate(SYNTHETIC_MEMORIES[:15]):
            if i >= j:
                continue
            shared = set(mem.get("tags", [])) & set(other.get("tags", []))
            if shared:
                edges.append({
                    "id": f"tag_{i}_{j}",
                    "source": f"mem_{mem['id']}",
                    "target": f"mem_{other['id']}",
                    "label": "shared topic",
                    "data": {"score": len(shared) / max(len(mem.get("tags", [1])), 1), "relType": "shared_tag"},
                })

    return {"nodes": nodes, "edges": edges, "total_memories": len(SYNTHETIC_MEMORIES)}


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/connections",
    summary="Memory relationship graph",
    description=(
        "Returns nodes (Memory + Entity) and edges (relationships) for the "
        "graph visualizer. Uses real DB data when memories have been uploaded, "
        "otherwise returns a demo graph from synthetic data."
    ),
)
def get_connections(
    include_entities: bool = Query(default=True, description="Include entity nodes"),
    limit: int = Query(default=100, ge=1, le=500, description="Max memories to include"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    count = db.query(Memory).count()

    if count == 0:
        return _synthetic_demo_graph()

    # Real DB graph
    memories = db.query(Memory).order_by(Memory.created_at.desc()).limit(limit).all()
    relationships = db.query(Relationship).all()

    nodes: List[Dict] = [_memory_node(m) for m in memories]
    edges: List[Dict] = []

    # Memory–Relationship edges
    for i, rel in enumerate(relationships):
        edges.append(_relationship_edge(rel, i))

    # Entity nodes and memory–entity edges
    if include_entities:
        seen_entity_ids: set = set()
        me_idx = 0
        for m in memories:
            for e in m.entities:
                if e.id not in seen_entity_ids:
                    seen_entity_ids.add(e.id)
                    nodes.append(_entity_node(e))
                edges.append(_entity_memory_edge(m, e, me_idx))
                me_idx += 1

    # Phase D: Build stories (temporal session groups)
    stories_raw = build_stories(db, limit=limit)
    stories = [
        {
            "id": s.id,
            "title": s.title,
            "memory_ids": s.memory_ids,
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "tags": s.tags,
            "memory_count": len(s.memory_ids),
        }
        for s in stories_raw
    ]

    # Phase D: Build project clusters
    project_clusters_raw = build_project_clusters(db)
    projects = [
        {"name": name, "memory_ids": ids, "memory_count": len(ids)}
        for name, ids in project_clusters_raw.items()
        if len(ids) >= 2  # only show projects with at least 2 memories
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "total_memories": count,
        "stories": stories,
        "projects": projects,
    }

