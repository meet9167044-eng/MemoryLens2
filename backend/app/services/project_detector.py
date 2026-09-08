"""
Phase D - Project Detector
===========================
Automatically groups Memories into logical Project nodes based on
tags, domain patterns, and technology entity overlap.

Heuristics (priority order):
  1. Tag hints: project-*, hackathon, internship, devjam, build-*
  2. Domain hint: GitHub/GitLab repo slug
  3. Auto fallback: app_detected name  (Fix 1.3)
  4. Auto fallback: root domain name   (Fix 1.3)"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.entity import Entity
from app.models.project import Project

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


# ── Fix 1.3: Auto-detect project from app or domain when tags give no hint ──

# Apps that are too generic to be useful project names
_GENERIC_APPS = frozenset({
    "unknown", "other", "", "chrome", "firefox", "safari",
    "edge", "browser", "system", "desktop",
})


def _auto_project_from_app(memory: Memory) -> Optional[str]:
    """
    Fix 1.3 fallback: create a project named after the detected app or domain.
    Covers the common case where the LLM generates generic tags (code, python,
    debugging) that don't match any of the narrow _PROJECT_TAG_PREFIXES.
    """
    app = (memory.app_detected or "").strip()
    if app and app.lower() not in _GENERIC_APPS:
        return app.title()  # e.g. "VS Code", "Cursor", "Figma"

    domain = (memory.domain or "").strip().lower()
    if domain and domain not in _GENERIC_APPS:
        # Use root domain: "github.com" → "Github", "docs.google.com" → "Docs Google"
        root = domain.split(".")[0]
        if root and root not in ("www", "app", "api", ""):
            return root.replace("-", " ").title()

    return None


def detect_projects_for_memory(db: Session, memory_id: UUID) -> Optional[str]:
    """Return a project name hint for a single Memory, and persist it to the DB."""
    memory: Optional[Memory] = db.get(Memory, memory_id)
    if not memory:
        return None
        
    # Fix 1.3: try specific tag/domain hints first, then fall back to app/domain auto-detect
    hint = _extract_project_hint(memory) or _auto_project_from_app(memory)
            
    if hint:
        # Create or fetch project
        project = db.query(Project).filter(Project.name == hint).first()
        if not project:
            project = Project(name=hint)
            db.add(project)
            db.flush()
            
        # Link memory to project
        if memory not in project.memories:
            project.memories.append(memory)
            db.commit()
            
        logger.info("detect_projects: memory=%s -> project=%r", memory_id, hint)
    return hint


def build_project_clusters(db: Session) -> dict:
    """
    Fetch persisted projects and return {project_name: [memory_id_str, ...]} clusters.
    """
    projects = db.query(Project).all()
    clusters: dict = {}

    for project in projects:
        memory_ids = [str(m.id) for m in project.memories]
        if memory_ids:
            clusters[project.name] = memory_ids

    logger.info("build_project_clusters: returned %d persisted projects", len(clusters))
    return clusters


def rebuild_all_projects(db: Session):
    """
    Rebuilds all projects from scratch.
    """
    logger.info("rebuild_all_projects: starting rebuild")
    # Delete all project links and projects
    db.execute(Project.__table__.delete())
    db.commit()

    memories = db.query(Memory).all()
    for mem in memories:
        detect_projects_for_memory(db, mem.id)
        
    logger.info("rebuild_all_projects: complete")