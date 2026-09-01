# MemoryLens — Correction & Implementation Plan

Master checklist. **Phases A–H are done.** Remaining work is **Phases I–N** (honest search, graph v2, honest UX, local OCR, docs). File-level actions for I–N live in [`implementation_plan.md`](implementation_plan.md).

This document tracks progress. Mark boxes here as work lands.

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

## Phase E: Auto-Ingestion ✅ COMPLETE
*Goal: Automate screenshot ingestion by watching folders.*

- `[x]` **Folder Watcher**: Implemented daemon using `watchdog` in `backend/app/services/folder_watcher.py`.
- `[x]` **Bulk Import API**: Added `/api/v1/ingest/bulk` endpoint to `backend/app/api/v1/ingest.py`.
- `[x]` **Watch Controller API**: Added `/api/v1/watch`, `/watch/start`, `/watch/stop` in `backend/app/api/v1/watch.py`.
- `[x]` **Settings UI**: Built full Settings page with Auto-capture toggle, folder path input, start/stop controls, and bulk import panel.

## Phase F: Scalability ✅ COMPLETE
*Goal: Handle 10,000+ screenshots smoothly.*

- `[x]` **Pipeline Queue**: Replaced raw threads with a proper in-process `PriorityQueue` in `backend/app/jobs/queue.py` and hooked it to FastAPI lifespan.
- `[x]` **Optimize Relationships**: Rewrote candidate selection in `compute_relationships_for_memory` to pre-fetch via temporal bounds, exact domains, entity overlaps, tag matches, and pgvector nearest-neighbor, completely avoiding O(n²) comparisons.
- `[x]` **Hash Column**: `file_hash` is present in `Screenshot` model and used for fast deduplication at ingest.

## Phase G: UX Polish ✅ COMPLETE
*Goal: Final touches on search, chat, and timeline.*

- `[x]` **NL Query Parsing**: Extract intents (dates, entities) from user search queries via `nl_parser.py`.
- `[x]` **Related Screenshots**: Added a right-hand sidebar to `MemoryDetail.tsx` showing linked screenshots.
- `[x]` **Timeline UI**: Added a 12-week GitHub-style calendar heatmap to `Timeline.tsx`.
- `[x]` **Contextual Chat**: Passed previous search results into the chat context in `Chat.tsx` via local storage.
- `[x]` **Search Facets**: Added clickable filter sidebars for Apps and Dates to `Search.tsx`.

## Phase H: Demo & Polish ✅ COMPLETE
*Goal: Ensure the project is portfolio-ready.*

- `[x]` **Demo Data Script**: Created `scripts/seed_demo.py` — seeds 50 realistic memories across 5 storylines (CUDA debugging, Google internship, GitHub code review, system setup, study session) with entities and relationships directly into PostgreSQL.
- `[x]` **Demo Script**: Created `scripts/demo_flow.md` — 8-scene guided walkthrough (Search → Memory Detail → Knowledge Graph → Timeline → Chat → Insights) with talking points and Q&A.
- `[x]` **README Overhaul**: Rewrote `README.md` to a punchy pitch with badges, architecture diagram, quick-start (5 commands), feature list, tech stack table, API reference, and demo section.

## Remaining Gaps After Phases A–H (Sept 2026 audit)

Phases A–H shipped the skeleton of the engine. These gaps are still open and are the reason the original audit is **not fully solved**:

| Gap | Why it still matters |
|---|---|
| Search loads every memory, then re-ranks in Python | pgvector/HNSW exists but is not used as ANN top-K — still O(n) |
| Chat RAG reads `embedding_placeholder` JSON | Semantic chat ignores the real `embedding` column |
| Search date filters use `created_at` | “Internship from January” filters upload time, not screenshot time |
| Synthetic search fallback when DB is empty | Search looks populated; Memories/Timeline look empty |
| Insights UI hardcodes `98.2%` OCR | Backend already returns `avg_confidence`; frontend ignores it |
| Connections is still a card grid | Tabs exist; no force-directed graph; no first-class project/person/domain tables |
| PaddleOCR commented out in `requirements.txt` | Local OCR path exists in code but is not installable from deps |
| Dead frontend data layer | `memoryService.ts` + `mockMemories.ts` unused by live routes |
| Stale docs | `docs/PRODUCT.md`, `docs/PROJECT.md`, `docs/STATUS.md` still say frontend-only |

---

## Phase I: Extra Improvements ⬜ PENDING
*Goal: Small robustness items left from the original plan.*

- `[ ]` **Entity Normalization**: New `backend/app/services/entity_normalizer.py` — merge aliases (`vscode` / `VS Code` / `Visual Studio Code`) before insert.
- `[ ]` **Rate Limiting**: `slowapi` on ingest (`10 uploads / min / IP`).
- `[ ]` **Job Visibility**: Upload modal polls `GET /api/v1/ingest/{screenshot_id}` every 2s and shows stage: Preprocessing → OCR → AI → Embedding → Indexing.
- `[ ]` **App filter on search**: Support `?app=VS Code` → `Memory.app_detected.ilike(...)`.

---

## Phase J: Search v2 — Honest ANN Retrieval ⬜ PENDING
*Goal: “Find the CUDA error screenshot” is O(log n) at 5,000+ rows, and chat uses the same vectors as search.*

- `[ ]` **ANN top-K in `db_search.py`**: `ORDER BY embedding <=> :query_vec LIMIT k` (k ≈ 50–100), then hybrid re-rank (0.6 cosine + 0.4 keyword/FTS). Do **not** load the full table.
- `[ ]` **PostgreSQL FTS**: Add `tsvector` (or `to_tsvector` on title/summary/ocr) and mix `ts_rank` into hybrid score instead of Python substring hits only.
- `[ ]` **Date filters on `captured_at`**: Replace `Memory.created_at` bounds in `db_search.py` with `Memory.captured_at` (fallback to `created_at` if null).
- `[ ]` **Chat retrieval on `memory.embedding`**: Rewrite `backend/app/api/v1/chat.py` to use pgvector cosine, not `json.loads(embedding_placeholder)`.
- `[ ]` **Drop synthetic search fallback**: `_pick_service()` always uses `DBSearchService`. Empty DB → empty results, same as Memories/Timeline.
- `[ ]` **Deprecate `embedding_placeholder`**: Stop writing it; optional later migration to drop the column.
- `[ ]` **Tests**: `tests/test_pgvector_search.py` — ANN ordering, date filter on `captured_at`, empty-DB returns `total=0`.

**Acceptance:** 1,000 seeded memories; search “CUDA error” returns the right row in the first page without loading all rows into Python.

---

## Phase K: Knowledge Graph v2 — First-Class Nodes + Real Graph UI ⬜ PENDING
*Goal: Close the differentiator. “Show everything related to my internship from January” is a graph query, not tag overlap.*

- `[ ]` **Project table**: `projects` + `memory_projects` association (name, description, color, confidence). Persist `project_detector` output instead of computing only at read time.
- `[ ]` **Person / Domain nodes**: Either dedicated tables or typed graph nodes stored from entities (`PERSON`) and `memory.domain`. Expose as node types in the Connections API.
- `[ ]` **Story persistence**: `stories` table from `story_builder.py` (title, date_start, date_end, memory_ids). Rebuild on ingest / nightly, not only on GET.
- `[ ]` **Semantic threshold**: Lower `_score_semantic` gate from `0.75` → `0.65` so related-but-not-identical screenshots still link.
- `[ ]` **NL + graph path**: Query “internship from January” → date window on `captured_at` + project/story/entity filter, then related memories.
- `[ ]` **Force graph UI**: Replace Connections card grid with `react-force-graph-2d` (or `@react-sigma/core`). Node types: memory / entity / project / domain. Edge color by `rel_type`. Click = 1-hop highlight.
- `[ ]` **Tests**: `tests/test_relationships_v2.py` — semantic + temporal + domain rows created; project association persisted.

**Acceptance:** Demo set shows internship screenshots clustered as a project/story; Connections renders an interactive graph, not only cards.

---

## Phase L: Honest UX ⬜ PENDING
*Goal: No fake metrics, no split empty states.*

- `[ ]` **Insights OCR card**: Bind to `insights.avg_confidence` (percent). If null, hide the card or show “No OCR confidence yet” — never `98.2%`.
- `[ ]` **Insights week delta**: Use `recent_activity_count` or hide “+12% from last week”.
- `[ ]` **Insights chart**: Plot last-7-day counts from the API, or remove the placeholder chart.
- `[ ]` **Consistent empty states**: Search, Memories, Timeline, Connections, Insights all show the same “upload to get started” empty state when `total_memories == 0`.
- `[ ]` **Delete dead data layer**: Remove `src/services/memoryService.ts` and `src/data/mockMemories.ts` if no live import remains.

**Acceptance:** Insights with a failed/empty pipeline never shows 98.2%. Empty DB looks empty on every page.

---

## Phase M: Local OCR & Offline Path ⬜ PENDING
*Goal: App runs without Gemini for OCR + embeddings. Still no model training.*

- `[ ]` **Uncomment PaddleOCR** in `backend/requirements.txt` (optional extra / documented install). Keep it optional so Windows users without Paddle can still use LLM OCR.
- `[ ]` **Three-tier OCR in pipeline**: PaddleOCR if installed → LLM vision OCR → empty string with a logged warning (never silent success with blank text).
- `[ ]` **Honor `EMBEDDING_PROVIDER=local`**: Pipeline `_compute_embedding()` tries local SentenceTransformers first when set, then Gemini.
- `[ ]` **Document in `DEVELOPER.md`**: How to install Paddle vs cloud-only path.

**Acceptance:** With no `GEMINI_API_KEY`, upload still produces embeddings (local) and some OCR text (Paddle) or a clear stage error.

---

## Phase N: Docs Truth ⬜ PENDING
*Goal: Docs match the running app.*

- `[ ]` **Rewrite `docs/PRODUCT.md` / `docs/PROJECT.md`**: Remove “frontend only, no backend”. Point to `DEVELOPER.md`.
- `[ ]` **Fix `docs/STATUS.md`**: Replace Review-1 frontend checklist with pointer to root `STATUS.md`.
- `[ ]` **Fix root `STATUS.md`**: Remove contradictory unchecked Phase B items; mark Phase C as **partial** (column+HNSW yes, ANN search no); mark Phase E/H from Correction_Plan; add Phases J–N as pending.
- `[ ]` **Keep `DEVELOPER.md` canonical**: Env vars, `alembic upgrade head`, `uvicorn app.main:app`, `npm run dev`, seed_demo, watch API.

**Acceptance:** A new contributor can run the app from `DEVELOPER.md` without reading an 800-line vision doc.

---

## Suggested order (if you only have 2 weeks)

| Week | Phases | Outcome |
|---|---|---|
| Week 1 | J + L | Search/chat are honest and scale; Insights stops lying |
| Week 2 | K (graph tables + force UI) | Differentiator is visible |
| After | I, M, N | Offline OCR, polish, docs |

Skip auth, Redis/Celery, and OS screenshot hooks until J + K work on ~50–1,000 uploaded screenshots.
