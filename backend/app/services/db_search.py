"""
DBSearchService — Phase J: bounded hybrid search.

Does not load the full memories table. Candidates come from:
  1. pgvector ANN (cosine distance, top-K) when a query vector exists
  2. Keyword ILIKE matches (top-K)
  3. Bounded fallback (recent embedded rows) if pgvector operators fail (SQLite)

Hybrid score = 0.6 × semantic + 0.4 × keyword, computed only on that candidate set.
Date filters use captured_at (screenshot time), falling back to created_at.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.memory import Memory
from app.schemas.search import (
    EntityResult,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SourceResult,
)

logger = logging.getLogger(__name__)

ANN_K = 80
KEYWORD_K = 80


def _embed_query(q: str) -> Optional[list]:
    """Embed a query string using Gemini, then local SentenceTransformers."""
    try:
        from app.config import settings
        if settings.GEMINI_API_KEY:
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            result = client.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=q,
            )
            return result.embeddings[0].values
    except Exception as exc:
        logger.warning("Gemini embedding failed: %s", exc)

    from app.core.local_embedder import embed_local
    return embed_local(q)


def _as_vector_list(value) -> Optional[list]:
    if value is None:
        return None
    if isinstance(value, str):
        import json
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else None
        except (json.JSONDecodeError, TypeError):
            return None
    try:
        return list(value)
    except (TypeError, ValueError):
        return None


def _cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (mag_a * mag_b)))


def _keyword_hit(q: str, memory: Memory) -> float:
    terms = [t for t in re.split(r"[^a-z0-9]+", q.lower()) if t]
    if not terms:
        return 0.0

    doc_parts = [
        memory.title or "",
        memory.summary or "",
        memory.raw_ocr_text or "",
        " ".join(memory.tags or []),
    ]
    ent_names = [e.name.lower() for e in (memory.entities or [])]
    full_doc = (" ".join(doc_parts) + " " + " ".join(ent_names)).lower()
    hits = sum(1 for t in terms if t in full_doc)
    return hits / len(terms)


def _make_snippet(q: str, memory: Memory, max_chars: int = 200) -> str:
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


_ENTITY_TYPE_MAP = {
    "organization": "company",
    "technology": "technology",
    "person": "person",
    "file_path": "other",
    "url": "other",
    "date": "other",
    "location": "other",
    "code_symbol": "other",
    "other": "other",
}


def _normalize_entity_type(raw: str) -> str:
    return _ENTITY_TYPE_MAP.get(raw, "other")


_CONTENT_TYPE_MAP = {
    "browser": "browser",
    "terminal": "terminal",
    "document": "document",
    "desktop": "desktop",
    "code": "desktop",
    "error": "terminal",
    "other": "other",
}


def _normalize_content_type(raw: str | None) -> str:
    return _CONTENT_TYPE_MAP.get(raw or "other", "other")


def _parse_iso_date(value: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _effective_timestamp(memory: Memory):
    return memory.captured_at or memory.created_at


def _to_search_result(memory: Memory, score: float, match_type: str, q: str) -> SearchResult:
    entities = [
        EntityResult(
            id=str(e.id),
            name=e.name,
            type=_normalize_entity_type(e.entity_type.value),
        )
        for e in (memory.entities or [])
    ]
    screenshot_id = str(memory.screenshot_id) if memory.screenshot_id else ""
    ts = _effective_timestamp(memory)
    timestamp = ts.isoformat() if ts else ""
    app_name = memory.app_detected or "Unknown"

    return SearchResult(
        id=str(memory.id),
        timestamp=timestamp,
        source=SourceResult(app=app_name, type=_normalize_content_type(memory.content_type)),
        title=memory.title or "Untitled",
        summary=memory.summary or "",
        ocr_snippet=_make_snippet(q, memory),
        tags=memory.tags or [],
        entities=entities,
        image_url=f"/api/v1/screenshots/{screenshot_id}/image",
        relevance_score=round(score, 4),
        match_type=match_type,  # type: ignore[arg-type]
    )


def _keyword_clause(q: str):
    terms = [t for t in re.split(r"[^a-z0-9]+", q.lower()) if len(t) > 1][:8]
    if not terms:
        return None
    clauses = []
    for t in terms:
        pat = f"%{t}%"
        clauses.append(
            or_(
                Memory.title.ilike(pat),
                Memory.summary.ilike(pat),
                Memory.raw_ocr_text.ilike(pat),
            )
        )
    return or_(*clauses)

def _fts_components(q: str):
    terms = [t for t in re.split(r"[^a-z0-9]+", q.lower()) if len(t) > 1][:8]
    if not terms:
        return None, None
    fts_query = ' & '.join(terms)
    # create tsvector from title, summary, and ocr
    tsvec = func.to_tsvector('english', func.coalesce(Memory.title, '') + ' ' + func.coalesce(Memory.summary, '') + ' ' + func.coalesce(Memory.raw_ocr_text, ''))
    tsq = func.to_tsquery('english', fts_query)
    return tsvec, tsq


class DBSearchService:
    """Bounded hybrid search over Memory rows (ANN top-K + keyword top-K)."""

    def __init__(self, db: Session):
        self.db = db
        self.parsed_nlp = None

    def _apply_filters(self, query, request: SearchRequest):
        from app.models.project import Project
        from app.models.story import Story
        ts = func.coalesce(Memory.captured_at, Memory.created_at)

        if request.date_from:
            dt_from = _parse_iso_date(request.date_from)
            if dt_from:
                query = query.filter(ts >= dt_from)
        if request.date_to:
            dt_to = _parse_iso_date(request.date_to)
            if dt_to:
                if len(request.date_to) <= 10:
                    dt_to = dt_to + timedelta(days=1)
                query = query.filter(ts < dt_to)
        if request.source_type:
            query = query.filter(Memory.content_type == request.source_type)
        if request.app:
            query = query.filter(Memory.app_detected.ilike(f"%{request.app}%"))
        elif getattr(self, "parsed_nlp", None) and self.parsed_nlp.get("app"):
            query = query.filter(Memory.app_detected.ilike(f"%{self.parsed_nlp['app']}%"))
            
        if request.project:
            query = query.filter(Memory.projects.any(Project.name.ilike(f"%{request.project}%")))
        elif getattr(self, "parsed_nlp", None) and self.parsed_nlp.get("project"):
            query = query.filter(Memory.projects.any(Project.name.ilike(f"%{self.parsed_nlp['project']}%")))
            
        if request.story:
            query = query.filter(Memory.stories.any(Story.title.ilike(f"%{request.story}%")))
        elif getattr(self, "parsed_nlp", None) and self.parsed_nlp.get("story"):
            query = query.filter(Memory.stories.any(Story.title.ilike(f"%{self.parsed_nlp['story']}%")))
            
        return query

    def _facets(self, request: SearchRequest) -> dict:
        base = self._apply_filters(self.db.query(Memory), request)
        facets = {"apps": {}, "dates": {}, "types": {}}

        try:
            for app, n in (
                base.with_entities(Memory.app_detected, func.count(Memory.id))
                .group_by(Memory.app_detected)
                .all()
            ):
                facets["apps"][app or "Unknown"] = n
            for typ, n in (
                self._apply_filters(self.db.query(Memory), request)
                .with_entities(Memory.content_type, func.count(Memory.id))
                .group_by(Memory.content_type)
                .all()
            ):
                facets["types"][typ or "other"] = n
        except Exception as exc:
            logger.debug("Facet aggregation failed: %s", exc)

        return facets

    def _ann_candidates(
        self,
        filtered,
        query_vec: list,
    ) -> Tuple[dict, dict]:
        """Return {id: Memory}, {id: sem_score} using pgvector, or bounded fallback."""
        by_id: dict = {}
        sem_scores: dict = {}
        try:
            dist_expr = Memory.embedding.cosine_distance(query_vec)
            rows = (
                filtered.filter(Memory.embedding.isnot(None))
                .order_by(dist_expr)
                .limit(ANN_K)
                .with_entities(Memory, dist_expr.label("dist"))
                .all()
            )
            for mem, dist_val in rows:
                by_id[mem.id] = mem
                try:
                    sem_scores[mem.id] = max(0.0, min(1.0, 1.0 - float(dist_val)))
                except (TypeError, ValueError):
                    pass
            return by_id, sem_scores
        except Exception as exc:
            logger.debug("pgvector ANN unavailable (%s); using bounded recent-row fallback", exc)

        recent = (
            filtered.filter(Memory.embedding.isnot(None))
            .order_by(func.coalesce(Memory.captured_at, Memory.created_at).desc())
            .limit(ANN_K)
            .all()
        )
        for mem in recent:
            by_id[mem.id] = mem
            stored = _as_vector_list(mem.embedding)
            if stored:
                sem_scores[mem.id] = _cosine(query_vec, stored)
        return by_id, sem_scores

    def search(self, request: SearchRequest) -> SearchResponse:
        from app.services.nl_parser import parse_search_query

        q = request.q.strip()
        nlp_applied = False

        if q and not (request.date_from or request.date_to or request.source_type or request.app or request.project or request.story):
            parsed = parse_search_query(q)
            if parsed.get("date_from") or parsed.get("app") or parsed.get("tags") or parsed.get("project") or parsed.get("story"):
                request.date_from = parsed.get("date_from") or request.date_from
                request.date_to = parsed.get("date_to") or request.date_to
                request.app = parsed.get("app") or request.app
                request.project = parsed.get("project") or request.project
                request.story = parsed.get("story") or request.story
                q = parsed.get("query", q).strip()
                nlp_applied = True
                self.parsed_nlp = parsed
            else:
                self.parsed_nlp = None
        else:
            self.parsed_nlp = None

        query_vec = _embed_query(q) if q else None

        filtered = self._apply_filters(
            self.db.query(Memory).options(joinedload(Memory.entities)),
            request,
        )

        by_id: dict = {}
        sem_scores: dict = {}

        if query_vec:
            by_id, sem_scores = self._ann_candidates(filtered, query_vec)

        tsvec, tsq = _fts_components(q) if q else (None, None)
        if tsvec is not None and tsq is not None:
            try:
                kw_rows = (
                    filtered.filter(tsvec.op('@@')(tsq))
                    .order_by(func.ts_rank(tsvec, tsq).desc())
                    .limit(KEYWORD_K)
                    .all()
                )
                for mem in kw_rows:
                    by_id[mem.id] = mem
            except Exception as exc:
                logger.debug("pg FTS unavailable (%s); fallback to ilike", exc)
                kw_clause = _keyword_clause(q)
                if kw_clause is not None:
                    kw_rows = (
                        filtered.filter(kw_clause)
                        .order_by(func.coalesce(Memory.captured_at, Memory.created_at).desc())
                        .limit(KEYWORD_K)
                        .all()
                    )
                    for mem in kw_rows:
                        by_id[mem.id] = mem
        else:
            kw_clause = _keyword_clause(q)
            if kw_clause is not None:
                kw_rows = (
                    filtered.filter(kw_clause)
                    .order_by(func.coalesce(Memory.captured_at, Memory.created_at).desc())
                    .limit(KEYWORD_K)
                    .all()
                )
                for mem in kw_rows:
                    by_id[mem.id] = mem

        candidates = list(by_id.values())
        facets = self._facets(request)

        # Date facet from candidates (captured_at)
        for m in candidates:
            ts = _effective_timestamp(m)
            if ts:
                date_str = ts.strftime("%Y-%m-%d")
                facets["dates"][date_str] = facets["dates"].get(date_str, 0) + 1

        # Calculate FTS ranks for all candidates if possible
        kw_scores = {}
        if tsvec is not None and tsq is not None and candidates:
            try:
                candidate_ids = [m.id for m in candidates]
                rank_rows = (
                    self.db.query(Memory.id, func.ts_rank(tsvec, tsq).label("rank"))
                    .filter(Memory.id.in_(candidate_ids))
                    .all()
                )
                for r in rank_rows:
                    kw_scores[r.id] = max(0.0, min(1.0, float(r.rank) * 2.0)) # rough normalization
            except Exception:
                pass

        scored: List[Tuple[float, str, Memory]] = []
        for mem in candidates:
            sem = sem_scores.get(mem.id, 0.0)
            if sem == 0.0 and query_vec:
                stored = _as_vector_list(mem.embedding)
                if stored:
                    sem = _cosine(query_vec, stored)
            
            # Use DB ts_rank if available, else python heuristic
            if mem.id in kw_scores:
                kw = kw_scores[mem.id]
            else:
                kw = _keyword_hit(q, mem) if q else 0.0

            score = 0.6 * sem + 0.4 * kw
            if not q or score >= 0.03:
                match_type = (
                    "hybrid" if sem > 0.3 and kw > 0.3
                    else ("semantic" if sem >= kw else "keyword")
                )
                scored.append((score, match_type, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        total = len(scored)
        page = scored[request.offset: request.offset + request.limit]
        results = [_to_search_result(m, s, mt, q) for s, mt, m in page]

        return SearchResponse(
            query=request.q,
            total=total,
            limit=request.limit,
            offset=request.offset,
            results=results,
            nlp_applied=nlp_applied,
            facets=facets,
        )


def retrieve_by_embedding(
    db: Session,
    query_vec: Optional[list],
    q: str,
    k: int = 5,
    exclude_ids: Optional[set] = None,
) -> List[Memory]:
    """Bounded ANN (+ keyword) retrieval for RAG chat. Never loads the full table."""
    exclude_ids = exclude_ids or set()
    filtered = db.query(Memory).options(joinedload(Memory.entities))
    service = DBSearchService(db)
    by_id: dict = {}
    sem_scores: dict = {}

    if query_vec:
        by_id, sem_scores = service._ann_candidates(filtered, query_vec)

    kw_clause = _keyword_clause(q)
    if kw_clause is not None:
        for mem in filtered.filter(kw_clause).limit(KEYWORD_K).all():
            by_id[mem.id] = mem

    ranked = []
    for mem in by_id.values():
        if str(mem.id) in exclude_ids:
            continue
        sem = sem_scores.get(mem.id, 0.0)
        if sem == 0.0 and query_vec:
            stored = _as_vector_list(mem.embedding)
            if stored:
                sem = _cosine(query_vec, stored)
        kw = _keyword_hit(q, mem) if q else 0.0
        ranked.append((0.6 * sem + 0.4 * kw, mem))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in ranked[:k]]
