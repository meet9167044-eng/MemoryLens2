"""
DBSearchService — Phase C: Real DB-backed Hybrid Keyword Search.

Searches across real Memory rows in PostgreSQL using keyword matching
on title, summary, ocr_text, tags, and entity names.

When Gemini embeddings are available, results are re-ranked by cosine
similarity computed in Python against stored embedding_placeholder JSON.

Falls back gracefully to the synthetic SearchService when the memories
table is empty (i.e., no files have been uploaded yet).
"""

from __future__ import annotations

import json
import math
import re
from typing import List, Optional, Tuple

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.entity import Entity
from app.models.relationship import Relationship
from app.schemas.search import (
    EntityResult,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SourceResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────




def _embed_query(q: str) -> Optional[list]:
    """Embed a query string using Gemini or local embedder."""
    try:
        from app.config import settings
        if settings.GEMINI_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            result = genai.embed_content(
                model=f"models/{settings.EMBEDDING_MODEL}",
                content=q,
                task_type="RETRIEVAL_QUERY",
            )
            return result["embedding"]
    except Exception:
        pass
    
    from app.core.local_embedder import embed_local
    return embed_local(q)


def _keyword_hit(q: str, memory: Memory) -> float:
    """Fraction of query terms found in the memory's text fields."""
    terms = [t for t in re.split(r"[^a-z0-9]+", q.lower()) if t]
    if not terms:
        return 0.0

    doc_parts = [
        memory.title or "",
        memory.summary or "",
        memory.raw_ocr_text or "",
        " ".join(memory.tags or []),
    ]
    doc = " ".join(doc_parts).lower()

    ent_names = [e.name.lower() for e in (memory.entities or [])]
    ent_doc = " ".join(ent_names)
    full_doc = doc + " " + ent_doc

    hits = sum(1 for t in terms if t in full_doc)
    return hits / len(terms)


def _make_snippet(q: str, memory: Memory, max_chars: int = 200) -> str:
    """Return the most relevant OCR excerpt or summary snippet."""
    ocr = memory.raw_ocr_text or ""
    if not ocr:
        return (memory.summary or "")[:max_chars]

    terms = [t for t in re.split(r"[^a-z0-9]+", q.lower()) if t]
    ocr_lower = ocr.lower()
    best_pos = len(ocr)
    for t in terms:
        pos = ocr_lower.find(t)
        if 0 <= pos < best_pos:
            best_pos = pos

    if best_pos < len(ocr):
        start = max(0, best_pos - 40)
        snippet = ocr[start: start + max_chars]
        return ("…" + snippet) if start > 0 else snippet
    return ocr[:max_chars]


def _to_search_result(memory: Memory, score: float, match_type: str, q: str) -> SearchResult:
    """Convert a Memory ORM row to a SearchResult Pydantic model."""
    entities = [
        EntityResult(id=str(e.id), name=e.name, type=e.entity_type.value)
        for e in (memory.entities or [])
    ]
    screenshot_id = str(memory.screenshot_id) if memory.screenshot_id else ""

    # Phase B: use captured_at (real screenshot time) over created_at (upload time)
    timestamp = (
        memory.captured_at.isoformat()
        if memory.captured_at
        else (memory.created_at.isoformat() if memory.created_at else "")
    )

    # Phase B: use the real app name extracted by LLM
    app_name = memory.app_detected or "Unknown"

    return SearchResult(
        id=str(memory.id),
        timestamp=timestamp,
        source=SourceResult(app=app_name, type=memory.content_type or "other"),
        title=memory.title or "Untitled",
        summary=memory.summary or "",
        ocr_snippet=_make_snippet(q, memory),
        tags=memory.tags or [],
        entities=entities,
        image_url=f"/api/v1/screenshots/{screenshot_id}/image",
        relevance_score=round(score, 4),
        match_type=match_type,  # type: ignore[arg-type]
    )



# ─────────────────────────────────────────────────────────────────────────────
# DB Search Service
# ─────────────────────────────────────────────────────────────────────────────

class DBSearchService:
    """
    Hybrid keyword + optional vector search over real Memory rows in PostgreSQL.

    Flow:
        1. Query Gemini for a query embedding (optional).
        2. Load all Memories matching keyword filters.
        3. Score each by: 0.6×semantic (cosine on stored embedding) + 0.4×keyword.
        4. Sort, paginate, return.
    """

    def __init__(self, db: Session):
        self.db = db

    def search(self, request: SearchRequest) -> SearchResponse:
        q = request.q.strip()
        query_vec = _embed_query(q)  # None if no API key

        # Base query — join entities for searching
        base = self.db.query(Memory)

        # Date filters
        if request.date_from:
            try:
                from datetime import datetime
                base = base.filter(Memory.created_at >= datetime.fromisoformat(request.date_from))
            except ValueError:
                pass
        if request.date_to:
            try:
                from datetime import datetime
                base = base.filter(Memory.created_at <= datetime.fromisoformat(request.date_to))
            except ValueError:
                pass
        if request.source_type:
            base = base.filter(Memory.content_type == request.source_type)

        if query_vec:
            distance_expr = Memory.embedding.cosine_distance(query_vec)
            sem_score_expr = (1.0 - distance_expr).label("sem_score")
            base = base.add_columns(sem_score_expr)
        else:
            from sqlalchemy import literal
            base = base.add_columns(literal(0.0).label("sem_score"))

        results_from_db = base.order_by(Memory.created_at.desc()).all()

        if not results_from_db:
            return SearchResponse(query=q, total=0, limit=request.limit, offset=request.offset, results=[])

        scored: List[Tuple[float, str, Memory]] = []

        for row in results_from_db:
            mem = row[0]
            sem = float(row[1]) if row[1] is not None else 0.0
            kw = _keyword_hit(q, mem)

            # Hybrid score
            score = 0.6 * sem + 0.4 * kw

            # Include if query is empty (browse mode) or score above threshold
            if not q or score >= 0.03:
                match_type = "hybrid" if sem > 0.3 and kw > 0.3 else ("semantic" if sem >= kw else "keyword")
                scored.append((score, match_type, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        total = len(scored)
        page = scored[request.offset: request.offset + request.limit]

        results = [_to_search_result(m, s, mt, q) for s, mt, m in page]

        return SearchResponse(
            query=q,
            total=total,
            limit=request.limit,
            offset=request.offset,
            results=results,
        )
