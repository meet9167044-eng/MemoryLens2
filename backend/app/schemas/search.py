"""
Pydantic models for Phase 8 — Semantic + Hybrid Search.

SearchRequest  — validated query parameters.
SearchResult   — a single ranked memory result (no raw vectors exposed).
SearchResponse — paginated container returned to the frontend.

Data structures mirror the TypeScript types in docs/DATA_SCHEMA.md so the
frontend can deserialise them without transformation.
"""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models (mirror DATA_SCHEMA.md)
# ---------------------------------------------------------------------------

class EntityResult(BaseModel):
    """A named entity extracted from a memory."""
    id: str
    name: str
    # Covers all EntityType enum values + legacy frontend types
    # Maps: organization→company, file_path/url/date/location/code_symbol→other
    type: str


class SourceResult(BaseModel):
    """Where the memory was captured."""
    app: str
    # Normalized to frontend-expected values; raw content_type mapped via _normalize_content_type()
    type: str


# ---------------------------------------------------------------------------
# Search request (validated query params)
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """
    Parameters accepted by GET /api/v1/search.

    q           — the natural-language query string (required, non-empty).
    limit       — max results to return (default 10, max 50).
    offset      — pagination offset (default 0).
    source_type — optional filter: only return memories from this source type.
    date_from   — optional ISO date string lower bound (inclusive).
    date_to     — optional ISO date string upper bound (inclusive).
    """
    q: str = Field(..., min_length=1, description="Search query (non-empty)")
    limit: int = Field(default=10, ge=1, le=50, description="Results per page")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    source_type: Optional[Literal[
        "desktop", "browser", "terminal", "document", "other"
    ]] = Field(default=None, description="Filter by source type")
    app: Optional[str] = Field(default=None, description="Filter by application name")
    project: Optional[str] = Field(default=None, description="Filter by project name")
    story: Optional[str] = Field(default=None, description="Filter by story title")
    date_from: Optional[str] = Field(
        default=None,
        description="ISO 8601 lower bound for timestamp (e.g. 2026-01-01)"
    )
    date_to: Optional[str] = Field(
        default=None,
        description="ISO 8601 upper bound for timestamp (e.g. 2026-12-31)"
    )


# ---------------------------------------------------------------------------
# Search result — one ranked memory (NO raw vectors)
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """
    A single memory returned by the search API.

    Raw embedding vectors are intentionally excluded — the frontend only
    needs human-readable fields and the relevance score.
    """
    id: str = Field(..., description="Memory ID (e.g. mem_1827)")
    timestamp: str = Field(..., description="ISO 8601 capture time")
    source: SourceResult
    title: str = Field(..., description="Short human-readable title")
    summary: str = Field(..., description="One-sentence description")
    ocr_snippet: str = Field(
        ...,
        description="First 200 chars of OCR text matching the query"
    )
    tags: List[str] = Field(default_factory=list)
    entities: List[EntityResult] = Field(default_factory=list)
    image_url: str = Field(..., description="Path to the screenshot image")
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Hybrid relevance score (0 = irrelevant, 1 = perfect match)"
    )
    match_type: Literal["semantic", "keyword", "hybrid"] = Field(
        ...,
        description="Dominant signal that drove this result"
    )


# ---------------------------------------------------------------------------
# Search response — paginated container
# ---------------------------------------------------------------------------

class SearchResponse(BaseModel):
    """
    Response envelope for GET /api/v1/search.
    """
    query: str = Field(..., description="Echo of the original query")
    total: int = Field(..., description="Total matching memories (before pagination)")
    limit: int
    offset: int
    results: List[SearchResult]
    nlp_applied: bool = Field(default=False, description="Whether NLP parsing extracted filters")
    facets: Optional[dict] = Field(default=None, description="Facet counts for the current search (apps, dates, tags)")
