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
from app.models.project import Project
from app.models.story import Story

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Response shapes (plain dicts — intentionally simple for graph lib flexibility)
# ─────────────────────────────────────────────────────────────────────────────

def _memory_node(m: Memory) -> Dict[str, Any]:
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

def _project_node(p: Project) -> Dict[str, Any]:
    return {
        "id": f"proj_{p.id}",
        "type": "project",
        "label": p.name,
        "data": {
            "projectId": str(p.id),
            "confidence": p.confidence,
        },
    }

def _story_node(s: Story) -> Dict[str, Any]:
    return {
        "id": f"story_{s.id}",
        "type": "story",
        "label": s.title,
        "data": {
            "storyId": str(s.id),
            "startTime": s.start_time.isoformat() if s.start_time else "",
            "endTime": s.end_time.isoformat() if s.end_time else "",
        },
    }

def _domain_node(domain: str) -> Dict[str, Any]:
    return {
        "id": f"dom_{domain}",
        "type": "domain",
        "label": domain,
        "data": {
            "domain": domain,
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

def _generic_edge(source_id: str, target_id: str, label: str, rel_type: str, edge_id: str) -> Dict[str, Any]:
    return {
        "id": edge_id,
        "source": source_id,
        "target": target_id,
        "label": label,
        "data": {"score": 1.0, "relType": rel_type},
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
    seen_domains: set = set()

    # Create dummy project for internship
    nodes.append({
        "id": "proj_internship",
        "type": "project",
        "label": "Internship Project",
        "data": {"confidence": 1.0}
    })
    
    # Create dummy story
    nodes.append({
        "id": "story_1",
        "type": "story",
        "label": "Demo Session",
        "data": {}
    })

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

        # Add to dummy story
        edges.append(_generic_edge(f"mem_{mem['id']}", "story_1", "in story", "has_story", f"ms_{i}"))

        # Add to internship project if tagged
        if "internship" in mem.get("tags", []):
            edges.append(_generic_edge(f"mem_{mem['id']}", "proj_internship", "in project", "has_project", f"mp_{i}"))

        domain = mem.get("source", {}).get("app", "").lower()
        if domain and domain not in ("unknown", ""):
            if domain not in seen_domains:
                seen_domains.add(domain)
                nodes.append(_domain_node(domain))
            edges.append(_generic_edge(f"mem_{mem['id']}", f"dom_{domain}", "has domain", "has_domain", f"md_{i}"))

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
            edges.append(_generic_edge(f"mem_{mem['id']}", f"ent_{ent_key}", "has entity", "has_entity", f"me_{i}_{ent_key}"))

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
        "Returns nodes (Memory, Entity, Project, Story, Domain) and edges for the "
        "graph visualizer. Uses real DB data when memories have been uploaded."
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
    projects = db.query(Project).all()
    stories = db.query(Story).order_by(Story.start_time.desc()).limit(limit).all()

    nodes: List[Dict] = []
    edges: List[Dict] = []
    
    seen_domains: set = set()

    for m in memories:
        nodes.append(_memory_node(m))
        
        # Virtual domain node
        domain = (m.domain or "").strip().lower()
        if domain and domain != "unknown":
            if domain not in seen_domains:
                seen_domains.add(domain)
                nodes.append(_domain_node(domain))
            edges.append(_generic_edge(f"mem_{m.id}", f"dom_{domain}", "has domain", "has_domain", f"md_{m.id}"))

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
                edges.append(_generic_edge(f"mem_{m.id}", f"ent_{e.id}", "has entity", "has_entity", f"me_{me_idx}"))
                me_idx += 1

    # Project nodes and edges
    mp_idx = 0
    for p in projects:
        nodes.append(_project_node(p))
        for m in p.memories:
            edges.append(_generic_edge(f"mem_{m.id}", f"proj_{p.id}", "in project", "has_project", f"mp_{mp_idx}"))
            mp_idx += 1

    # Story nodes and edges
    ms_idx = 0
    for s in stories:
        nodes.append(_story_node(s))
        for m in s.memories:
            edges.append(_generic_edge(f"mem_{m.id}", f"story_{s.id}", "in story", "has_story", f"ms_{ms_idx}"))
            ms_idx += 1

    # Format for backwards compatibility with the old UI (which expects these arrays)
    formatted_stories = []
    for s in stories:
        formatted_stories.append({
            "id": str(s.id),
            "title": s.title,
            "memory_ids": [str(m.id) for m in s.memories],
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "tags": [],
            "memory_count": len(s.memories),
        })

    formatted_projects = []
    for p in projects:
        formatted_projects.append({
            "name": p.name,
            "memory_ids": [str(m.id) for m in p.memories],
            "memory_count": len(p.memories),
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "total_memories": count,
        "stories": formatted_stories,
        "projects": formatted_projects,
    }

