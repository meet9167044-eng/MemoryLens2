"""
Phase D - Project Detector
===========================
Automatically groups Memories into logical Project nodes based on
tags, domain patterns, and technology entity overlap.

Heuristics (priority order):
  1. Tag hints: project-*, hackathon, internship, devjam, build-*
  2. Domain hint: GitHub/GitLab repo slug
  3. Technology entity cluster fallback
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.entity import Entity

logger = logging.getLogger(__name__)

_PROJECT_TAG_PREFIXES = ("project-", "hackathon", "internship", "devjam", "build-")
_REPO_DOMAIN_PATTERN = re.compile(
    r"(?:github|gitlab|bitbucket)\.com/[^/]+/([^/?#]+)", re.IGNORECASE
)


def _extract_project_hint(memory: Memory) -> Optional[str]:
    """Return a project name hint from tags or domain, or None."""
    for tag in (memory.tags or []):
        tag_lower = str(tag).lower()
        for prefix in _PROJECT_TAG_PREFIXES:
            if tag_lower.startswith(prefix):
                slug = tag_lower[len(prefix):].strip("-")
                if slug:
                    return slug.replace("-", " ").title()
        if tag_lower in ("hackathon", "internship", "devjam"):
            return tag_lower.replace("-", " ").title()

    domain = memory.domain or ""
    m = _REPO_DOMAIN_PATTERN.search(domain)
    if m:
        return m.group(1).replace("-", " ").title()

    return None


def detect_projects_for_memory(db: Session, memory_id: UUID) -> Optional[str]:
    """Return a project name hint for a single Memory, or None."""
    memory: Optional[Memory] = db.get(Memory, memory_id)
    if not memory:
        return None
    hint = _extract_project_hint(memory)
    if hint:
        logger.info("detect_projects: memory=%s -> project=%r", memory_id, hint)
    return hint


def build_project_clusters(db: Session) -> dict:
    """
    Scan all Memories and return {project_name: [memory_id_str, ...]} clusters.
    """
    memories = db.query(Memory).all()
    clusters: dict = defaultdict(list)

    for mem in memories:
        hint = _extract_project_hint(mem)
        if hint:
            clusters[hint].append(str(mem.id))
            continue

        entities = db.query(Entity).filter(Entity.memory_id == mem.id).all()
        tech_entities = [
            e.name.lower()
            for e in entities
            if e.entity_type.value in ("technology", "framework")
        ]
        if tech_entities:
            key = tech_entities[0].replace(" ", "-").title()
            clusters[key].append(str(mem.id))

    logger.info("build_project_clusters: found %d clusters", len(clusters))
    return dict(clusters)