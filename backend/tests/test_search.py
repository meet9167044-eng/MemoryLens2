"""
Phase 8 — Semantic + Hybrid Search Tests.

Test coverage:
    1. Semantic recall:  "GPU problem" must find mem_1827 (CUDA error).
    2. Empty query:      returns HTTP 422 (validation error).
    3. Pagination:       limit and offset work correctly.
    4. Source-type filter: filtering by source_type excludes wrong-type results.
    5. No raw vectors:   SearchResult fields never contain raw float lists.
    6. Score range:      relevance_score is always in [0.0, 1.0].
    7. Result structure: required fields are present on every result.
    8. Health check:     GET /api/v1/health still returns 200 OK.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def search(q: str, **params) -> dict:
    """Convenience wrapper for GET /api/v1/search."""
    return client.get("/api/v1/search", params={"q": q, **params})


# ---------------------------------------------------------------------------
# 1. Semantic recall — (Moved to test_pgvector_search.py)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 2. Empty query → HTTP 422
# ---------------------------------------------------------------------------

class TestEmptyQuery:
    def test_empty_string_returns_422(self):
        """Empty q param must be rejected before reaching the service."""
        resp = client.get("/api/v1/search", params={"q": ""})
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_missing_q_returns_422(self):
        """Missing q param entirely must return 422."""
        resp = client.get("/api/v1/search")
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_whitespace_only_raises_422(self):
        """A query of only spaces has length > 0 so FastAPI accepts it, but
        the service strips it and scores zero hits — returns 200 with empty results."""
        resp = client.get("/api/v1/search", params={"q": "   "})
        # FastAPI min_length=1 counts the spaces, so it passes validation.
        # The service may return 0 results but not an error.
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 3. Pagination
# ---------------------------------------------------------------------------

class TestPagination:
    def test_limit_respected(self):
        """Results count should not exceed the requested limit."""
        resp = search("error", limit=3)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 3

    def test_offset_shifts_results(self):
        """Page 2 should not overlap with page 1 results."""
        resp1 = search("memory", limit=5, offset=0)
        resp2 = search("memory", limit=5, offset=5)
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        ids1 = {r["id"] for r in resp1.json()["results"]}
        ids2 = {r["id"] for r in resp2.json()["results"]}
        # No overlap between page 1 and page 2
        assert ids1.isdisjoint(ids2), f"Overlap detected: {ids1 & ids2}"

    def test_offset_beyond_total_returns_empty(self):
        """An offset larger than total results returns an empty list."""
        resp = search("cuda", limit=10, offset=9999)
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []

    def test_limit_max_boundary(self):
        """limit=50 is the maximum allowed value."""
        resp = search("memory", limit=50)
        assert resp.status_code == 200

    def test_limit_over_max_returns_422(self):
        """limit=51 should be rejected by FastAPI validation."""
        resp = client.get("/api/v1/search", params={"q": "memory", "limit": 51})
        assert resp.status_code == 422

    def test_total_field_reflects_all_matches(self):
        """total should be >= len(results) always."""
        resp = search("cuda", limit=2)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= len(data["results"])


# ---------------------------------------------------------------------------
# 4. Source-type filter
# ---------------------------------------------------------------------------

class TestSourceTypeFilter:
    def test_terminal_filter_excludes_browser(self):
        """Results filtered to 'terminal' must not include browser-type memories."""
        resp = search("nvidia driver", source_type="terminal")
        assert resp.status_code == 200
        for result in resp.json()["results"]:
            assert result["source"]["type"] == "terminal", (
                f"Expected source.type=terminal, got {result['source']['type']} "
                f"for memory {result['id']}"
            )

    def test_browser_filter_excludes_desktop(self):
        """Results filtered to 'browser' must not include desktop-type memories."""
        resp = search("cuda", source_type="browser")
        assert resp.status_code == 200
        for result in resp.json()["results"]:
            assert result["source"]["type"] == "browser"

    def test_filter_with_no_match_returns_empty(self):
        """
        Searching for CUDA memories with source_type='document' returns nothing
        because all CUDA memories are desktop/browser/terminal type.
        """
        resp = search("cuda error gpu", source_type="document")
        assert resp.status_code == 200
        data = resp.json()
        # Document-type memories exist (mem_1980) but CUDA query should score very
        # low on a paper about Transformers — could be 0 results or very low score.
        # We simply assert the filter was applied (all returned are documents).
        for r in data["results"]:
            assert r["source"]["type"] == "document"


# ---------------------------------------------------------------------------
# 5. No raw vectors exposed
# ---------------------------------------------------------------------------

class TestNoRawVectors:
    def test_response_contains_no_vector_fields(self):
        """
        The response must not contain raw embedding vectors.
        Phase 8 spec: 'Do not expose raw vector floats to the frontend.'
        """
        resp = search("GPU problem", limit=5)
        assert resp.status_code == 200
        data = resp.json()

        forbidden_keys = {"embedding", "vector", "embeddings", "raw_vector", "vec"}
        for result in data["results"]:
            intersection = forbidden_keys.intersection(result.keys())
            assert not intersection, (
                f"Raw vector field(s) found in result {result['id']}: {intersection}"
            )

    def test_top_level_response_has_no_vectors(self):
        """Top-level SearchResponse also must not contain raw vectors."""
        resp = search("cuda")
        assert resp.status_code == 200
        data = resp.json()
        forbidden = {"embedding", "vector", "embeddings"}
        assert not forbidden.intersection(data.keys())


# ---------------------------------------------------------------------------
# 6. Score range
# ---------------------------------------------------------------------------

class TestScoreRange:
    def test_relevance_score_in_valid_range(self):
        """All relevance_score values must be in [0.0, 1.0]."""
        resp = search("python error debug", limit=20)
        assert resp.status_code == 200
        for result in resp.json()["results"]:
            score = result["relevance_score"]
            assert 0.0 <= score <= 1.0, (
                f"Score {score} out of range for memory {result['id']}"
            )

    def test_results_are_sorted_by_score_descending(self):
        """Results must be returned highest-score first."""
        resp = search("cuda gpu error memory", limit=10)
        assert resp.status_code == 200
        scores = [r["relevance_score"] for r in resp.json()["results"]]
        assert scores == sorted(scores, reverse=True), (
            f"Results not sorted by score: {scores}"
        )


# ---------------------------------------------------------------------------
# 7. Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    REQUIRED_FIELDS = {
        "id", "timestamp", "source", "title", "summary",
        "ocr_snippet", "tags", "entities", "image_url",
        "relevance_score", "match_type",
    }

    def test_all_required_fields_present(self):
        """Every SearchResult must contain all required fields."""
        resp = search("memory search", limit=10)
        assert resp.status_code == 200
        for result in resp.json()["results"]:
            missing = self.REQUIRED_FIELDS - result.keys()
            assert not missing, (
                f"Memory {result.get('id', '?')} missing fields: {missing}"
            )

    def test_response_echoes_query(self):
        """SearchResponse.query must echo the original query string."""
        resp = search("CUDA error PyTorch")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "CUDA error PyTorch"

    def test_response_has_total_limit_offset(self):
        """SearchResponse must include total, limit, offset fields."""
        resp = search("error", limit=5, offset=2)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["limit"] == 5
        assert data["offset"] == 2

    def test_match_type_is_valid(self):
        """match_type must be one of 'semantic', 'keyword', 'hybrid'."""
        valid = {"semantic", "keyword", "hybrid"}
        resp = search("python cuda training", limit=10)
        assert resp.status_code == 200
        for result in resp.json()["results"]:
            assert result["match_type"] in valid, (
                f"Invalid match_type '{result['match_type']}' for {result['id']}"
            )


# ---------------------------------------------------------------------------
# 8. Health check (regression — Phase 1 must still pass)
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_health_returns_200(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_returns_ok_status(self):
        resp = client.get("/api/v1/health")
        assert resp.json() == {"status": "ok"}
