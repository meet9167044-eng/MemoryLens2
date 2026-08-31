# MemoryLens — Correction & Implementation Plan

This document breaks down the end-to-end implementation plan into actionable, step-by-step phases. It will serve as our master checklist to track progress as we fix bugs and build out the knowledge graph engine.

## Phase A: Codebase Cleanup & Fixes ✅ COMPLETE
*Goal: Fix immediate bugs (missing metadata, invalid models) and remove dead code.*

- `[x]` **Fix LLM Extraction**: Updated `backend/.env` to use `llama-3.2-11b-vision-preview` (vision) and `llama-3.1-8b-instant` (chat) — this was the root cause of missing tags/summaries.
- `[x]` **Remove Dead Backend Stub**: Deleted `backend/main.py`.
- `[x]` **Remove Dead Frontend Pages**: Deleted `Overview.tsx`, `Connections.tsx`, `Memories.tsx`, `Timeline.tsx`, `Insights.tsx`.
- `[x]` **Create Developer Guide**: Created `DEVELOPER.md` at root with full setup instructions.
- `[x]` **Update Insights API**: Now returns real `avg_confidence`, `processing_success_rate`, `app_breakdown`.
- `[x]` **Update Status Doc**: Rewrote `STATUS.md` to reflect actual state.
- `[x]` **Fix Duplicate Ingestion**: Added SHA-256 hash check in ingest endpoint + `file_hash` column on `Screenshot` model. Migration `2c5f3091dea7` applied.
- `[x]` **Fix `file_size_bytes` type**: Changed from `String` to `Integer`.

## Phase B: Timestamps & App Detection ✅ COMPLETE
*Goal: Capture original timestamps from EXIF and persist detected apps.*

- `[x]` **Database Schema Update**: Added `app_detected`, `captured_at`, and `domain` columns to `Memory`.
- `[x]` **Alembic Migration**: Migration `2c766c3a59a7` generated and applied.
- `[x]` **EXIF Extraction**: `_preprocess()` in `pipeline.py` now extracts `captured_at` from EXIF → filename patterns → file mtime (priority order).
- `[x]` **Persist App Data**: `_ai_extraction()` in `pipeline.py` now saves `result.app_detected` to `memory.app_detected`.
- `[x]` **Search Integration**: `db_search.py` now uses `memory.app_detected` and `memory.captured_at` in search results.
- `[x]` **Memories API**: `memories.py` uses real `app_detected`, correct timestamp, and sorts by `captured_at` desc.
- `[x]` **Frontend types**: `InsightStats` interface updated to include all new API fields.

## Phase C: Real Vector Search ✅ COMPLETE
*Goal: Replace O(n) Python search with fast `pgvector` lookups.*

- `[x]` **Database Schema Update**: Add `embedding` column of type `Vector(768)` to `Memory`.
- `[x]` **Alembic Migration**: Generate migration to enable `pgvector` extension, add column, and create an HNSW index.
- `[x]` **Pipeline Update**: Update `_embedding()` in `pipeline.py` to store vectors in the new pgvector column.
- `[x]` **Local Embedder**: Implement SentenceTransformers in `backend/app/core/local_embedder.py` for offline embeddings.
- `[x]` **Search Overhaul**: Rewrite `backend/app/services/db_search.py` to use pgvector cosine operator (`<=>`) mixed with full-text search.
- `[x]` **Dependencies**: Add `sentence-transformers` to `requirements.txt`.

## Phase D: Knowledge Graph Engine ✅ COMPLETE
*Goal: Build the core differentiator—linking screenshots by semantics, time, projects, and domains.*

- `[x]` **Semantic Relationships**: Implemented `_score_semantic()` using pgvector cosine similarity in `backend/app/processing/relationships.py`.
- `[x]` **Temporal Relationships**: Implemented `_score_temporal()` using `captured_at` proximity (2-hour decay window).
- `[x]` **Project Nodes**: Created `project_detector.py` auto-detector with tag/domain/entity cluster heuristics.
- `[x]` **Domain Linking**: Extended LLM prompt to extract URLs/domains and added `_score_domain()` in relationship engine.
- `[x]` **Story Grouping**: Created `story_builder.py` to group temporally close memories into session stories.
- `[x]` **Graph UI**: Upgraded Connections page with tabbed Knowledge Graph / Stories / Projects view with relationship type legend.

## Phase E: Auto-Ingestion
*Goal: Automate screenshot ingestion by watching folders.*

- `[ ]` **Folder Watcher**: Implement a daemon using `watchdog` to monitor screenshot directories (`backend/app/services/folder_watcher.py`).
- `[ ]` **Bulk Import API**: Add a bulk import endpoint to `backend/app/api/v1/ingest.py`.
- `[ ]` **Watch Controller API**: Add endpoints to start/stop the folder watcher (`backend/app/api/v1/watch.py`).
- `[ ]` **Settings UI**: Add "Auto-capture" toggle in the frontend.

## Phase F: Scalability
*Goal: Handle 10,000+ screenshots smoothly.*

- `[ ]` **Pipeline Queue**: Replace raw threads with a proper in-process `asyncio.Queue` in `backend/app/jobs/queue.py`.
- `[ ]` **Optimize Relationships**: Rewrite relationship candidate selection to avoid O(n²) comparisons (use entity overlap / pgvector top-K).
- `[ ]` **Hash Column**: Add `file_hash` explicitly to the `Screenshot` model and use it for fast deduplication at ingest.

## Phase G: UX Polish
*Goal: Final touches on search, chat, and timeline.*

- `[ ]` **NL Query Parsing**: Extract intents (dates, entities) from user search queries.
- `[ ]` **Related Screenshots**: Add a sidebar to `MemoryDetail.tsx` showing linked screenshots.
- `[ ]` **Timeline UI**: Group memories by date and add a calendar heatmap.
- `[ ]` **Contextual Chat**: Pass previous search results into the chat context.
- `[ ]` **Search Facets**: Add clickable filter sidebars (App, Date, Tags, Entities).

## Phase H: Demo & Polish
*Goal: Ensure the project is portfolio-ready.*

- `[ ]` **Demo Data Script**: Write `scripts/seed_demo.py` to populate realistic fake memories.
- `[ ]` **Demo Script**: Write a step-by-step walkthrough in `scripts/demo_flow.md`.
- `[ ]` **README Overhaul**: Simplify `README.md` to a punchy pitch with quick start steps and an architecture diagram.

## Phase I: Extra Improvements
*Goal: Additional robust enhancements.*

- `[ ]` **Local OCR**: Re-enable PaddleOCR as a fallback local path.
- `[ ]` **Entity Normalization**: Build a normalizer to merge aliases (e.g., "vscode" and "VS Code").
- `[ ]` **Rate Limiting**: Add upload limits to the ingest API.
- `[ ]` **Job Visibility**: Poll pipeline status from the frontend upload modal to show actual progress.
