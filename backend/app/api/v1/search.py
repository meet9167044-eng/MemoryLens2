"""
GET  /api/v1/search        — Phase J: Hybrid DB-backed search (ANN + keyword)
POST /api/v1/search/hybrid — Same, body-based variant

Production always uses DBSearchService (empty DB → empty results).
Synthetic SearchService is only used when TESTING=1 so recall fixtures stay deterministic.
"""

from __future__ import annotations

import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search import SearchService
from app.services.db_search import DBSearchService

router = APIRouter()


def _pick_service(db: Session) -> object:
    """
    Production: always search the real database (empty library → empty results).
    Tests: keep the synthetic SearchService so Phase 8 recall fixtures stay stable.
    """
    if os.environ.get("TESTING") == "1":
        return SearchService()
    return DBSearchService(db)


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Hybrid semantic + keyword search over Memories",
    description=(
        "Searches uploaded memories with bounded pgvector ANN + keyword matching. "
        "An empty library returns zero results (no synthetic demo data)."
    ),
)
def search_memories(
    q: str = Query(..., min_length=1, description="Search query", example="GPU error in Python"),
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    source_type: Optional[Literal["desktop", "browser", "terminal", "document", "other"]] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="ISO 8601 lower bound"),
    date_to: Optional[str] = Query(default=None, description="ISO 8601 upper bound"),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Search memories using hybrid semantic + keyword ranking."""
    service = _pick_service(db)
    request = SearchRequest(q=q, limit=limit, offset=offset, source_type=source_type,
                             date_from=date_from, date_to=date_to)
    return service.search(request)


@router.post(
    "/search/hybrid",
    response_model=SearchResponse,
    summary="Hybrid search (body-based POST)",
    description="Same as GET /search but accepts query params in the request body for richer filter support.",
)
def search_hybrid(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    """POST version of hybrid search — accepts SearchRequest body."""
    service = _pick_service(db)
    return service.search(request)
