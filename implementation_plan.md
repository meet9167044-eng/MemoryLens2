# MemoryLens — Implementation Plan (Updated)

## Goal
Finish the engine, not the wrapper.

Target product: **search your screenshots through a knowledge graph of people / projects / websites / dates.**

Completed work lives in [`Correction_Plan.md`](Correction_Plan.md) (Phases A–H). This file is the **remaining** plan (Phases I–N) with file-level actions.

---

## Status as of Sept 2026 (after Phases A–H)

Phases A–H are implemented. The original audit is **not fully closed**. pgvector, relationship types, folder watch, and demo seed exist, but search is still a full-table hybrid scan, chat still uses the placeholder embedding column, Connections is still a card grid, and Insights still hardcodes OCR confidence.

### What actually works
| Piece | Status |
|---|---|
| Upload → pipeline queue → DB | Working |
| Groq / Gemini / OpenAI extractor | Working |
| `app_detected`, `captured_at`, `domain` persisted | Working |
| SHA-256 ingest dedup | Working |
| `memories.embedding` vector(768) + HNSW migration | Schema exists; pipeline writes it |
| Local SentenceTransformers fallback | `local_embedder.py` |
| Semantic / temporal / domain relationship scoring | Computed on ingest (candidate set, not all-pairs) |
| Project/story heuristics | Runtime only — not first-class tables |
| Folder watcher + bulk ingest + Settings UI | Working |
| Demo seed (`scripts/seed_demo.py`) | Working |
| `DEVELOPER.md` | Working |

### What is still broken / incomplete
| Piece | Gap |
|---|---|
| Hybrid search | SQL cosine is computed, then **all rows** are loaded and re-ranked in Python — still O(n) |
| Chat RAG | Reads `embedding_placeholder` JSON, not `memory.embedding` |
| Date filters | `db_search.py` filters `created_at`, not `captured_at` |
| Empty DB | Search falls back to synthetic data; other pages do not |
| Insights UI | Hardcoded `98.2%` OCR; “+12% from last week”; placeholder chart |
| Graph UI | Card grid + tabs — no force-directed graph |
| Graph model | No `projects` / `people` / `domains` / `stories` tables |
| Semantic links | Only stored if cosine ≥ 0.75 (too strict) |
| PaddleOCR | Code path exists; deps commented out in `requirements.txt` |
| Dead code | `src/services/memoryService.ts`, `src/data/mockMemories.ts` |
| Docs | `docs/PRODUCT.md`, `docs/PROJECT.md`, `docs/STATUS.md` still Review-1 / frontend-only |

Do **not** train a custom model. Remaining work is indexing, graph persistence, retrieval, and honest UI.

---

## Open questions (still relevant)

> **Q1 — Deployment?** Local-first until J+K work. Then Railway/Fly + Vercel if needed.

> **Q2 — Offline?** Keep SentenceTransformers as default local embedder. PaddleOCR is optional (Phase M).

> **Q3 — Graph UI?** Force-directed graph this round (Phase K), not another card layout.

> **Q4 — Time?** If 2 weeks: J + L in week 1, K in week 2. I / M / N after.

---

## Remaining phases

Each phase is independently shippable. File paths are relative to the repo root.

---

### Phase I — Extra Improvements (2–3 days) `Priority: LOW`

**Goal:** Leftover robustness from the original plan.

#### [NEW] `backend/app/services/entity_normalizer.py`
Alias map (`vscode` → `VS Code`, `python3` → `Python`). Call from `_ai_extraction()` before inserting `Entity` rows.

#### [MODIFY] `backend/app/api/v1/ingest.py`
Add `slowapi` (or equivalent) rate limit: 10 uploads / minute / IP.

#### [MODIFY] `src/components/upload/UploadModal.tsx`
Poll `GET /api/v1/ingest/{screenshot_id}` every 2s. Show current `JobStage`.

#### [MODIFY] `backend/app/api/v1/search.py` + `db_search.py`
Add `app` query param → `Memory.app_detected.ilike(...)`.

---

### Phase J — Search v2: Honest ANN Retrieval (3–5 days) `Priority: CRITICAL`

**Goal:** Sub-linear search at 5,000+ screenshots. Chat and search share one vector column.

#### [MODIFY] `backend/app/services/db_search.py`
Replace “score every row in Python” with:

1. Embed query (`_embed_query` — Gemini or `embed_local`).
2. ANN: `ORDER BY Memory.embedding.cosine_distance(query_vec) LIMIT k` (k = 50–100). Include rows with `embedding IS NULL` only via keyword/FTS branch, not the ANN branch.
3. Hybrid re-rank on that candidate set: `0.6 * (1 - cosine_distance) + 0.4 * keyword_or_ts_rank`.
4. Date filters on `Memory.captured_at` (fallback `created_at` if null).
5. Facets computed on the **filtered** candidate set or a cheap SQL `GROUP BY`, not a full table scan if avoidable.

#### [MODIFY] `backend/app/api/v1/chat.py`
In retrieval, use `memory.embedding` + the same cosine / pgvector path. Delete `json.loads(m.embedding_placeholder)`.

#### [MODIFY] `backend/app/api/v1/search.py`
`_pick_service()`: always `DBSearchService(db)` outside tests. Empty table → `total=0`, empty `results`. Keep synthetic `SearchService` only when `TESTING=1`.

#### [MODIFY] `backend/app/jobs/pipeline.py`
Stop writing `embedding_placeholder`. Only `memory.embedding`.

#### [NEW] `backend/tests/test_pgvector_search.py`
- ANN order: closer vector ranks higher
- `date_from` / `date_to` apply to `captured_at`
- Empty DB → empty response (no synthetic titles)

**Acceptance:** Seed 1,000 rows; “CUDA error” is on page 1; chat citations come from pgvector neighbors.

---

### Phase K — Knowledge Graph v2 (1–2 weeks) `Priority: CRITICAL`

**Goal:** First-class graph, not memory↔memory extras on a card grid.

#### [NEW] models + Alembic
- `backend/app/models/project.py` — `projects(id, name, description, color)`
- `backend/app/models/memory_project.py` — `memory_id`, `project_id`, `confidence`
- `backend/app/models/story.py` — `title`, `date_start`, `date_end`, `memory_ids` (JSONB)
- Optional `domains` table or typed nodes from `memory.domain`

#### [MODIFY] `backend/app/services/project_detector.py`
On ingest, upsert `Project` + `MemoryProject` instead of returning a name only at GET time.

#### [MODIFY] `backend/app/services/story_builder.py`
Persist `Story` rows (rebuild for the affected time window after each ingest).

#### [MODIFY] `backend/app/processing/relationships.py`
- Semantic persist threshold `0.65` (keep candidate ANN at top-50).
- Include project co-membership as a scoring signal or edge type if useful.

#### [MODIFY] `backend/app/api/v1/connections.py`
Return nodes: `memory | entity | project | domain` and edges with `rel_type` + `score`.

#### [MODIFY] `backend/app/services/db_search.py` + `nl_parser.py`
“Internship from January” → `captured_at` range + project/story/entity constraint, then related memories.

#### [MODIFY] `src/pages/Connections/Connections.tsx` + `package.json`
Add `react-force-graph-2d`. Replace the entity card grid with:

- Node color by type
- Edge color by `rel_type` (semantic / temporal / domain / shared_entity / shared_tag)
- Click → 1-hop highlight
- Keep Stories / Projects tabs as lists that focus the graph

#### [NEW] `backend/tests/test_relationships_v2.py`
Semantic, temporal, domain rows; project association after ingest.

**Acceptance:** Demo internship cluster is a project + story; Connections is an interactive graph.

---

### Phase L — Honest UX (1–2 days) `Priority: HIGH`

**Goal:** UI never invents metrics or demo data.

#### [MODIFY] `src/pages/Insights/Insights.tsx`
- OCR card: `insights.avg_confidence` → percent, or hide if null
- Remove hardcoded `98.2%` and `+12% from last week`
- Chart: last 7 days from API, or remove the placeholder

#### [MODIFY] Search / Memories / Timeline / Connections / Insights
Shared empty state when `total_memories === 0`.

#### [DELETE] if unused
`src/services/memoryService.ts`, `src/data/mockMemories.ts`

**Acceptance:** Failed OCR + empty DB cannot show 98.2% confidence or synthetic search hits.

---

### Phase M — Local OCR & Offline Path (2–3 days) `Priority: MEDIUM`

**Goal:** Inference only — PaddleOCR + SentenceTransformers. No training.

#### [MODIFY] `backend/requirements.txt`
Document optional:

```
# paddleocr>=2.7.0
# paddlepaddle>=2.6.0
```

Or an extras section in `DEVELOPER.md` (`pip install paddleocr paddlepaddle`).

#### [MODIFY] `backend/app/jobs/pipeline.py` OCR stage
1. PaddleOCR if importable  
2. Else LLM vision text  
3. Else fail the OCR stage **or** complete with empty text **and** a visible warning in job error

Never treat blank OCR as high-confidence success.

#### [MODIFY] `backend/app/jobs/pipeline.py` `_compute_embedding()`
If `EMBEDDING_PROVIDER=local`, call `embed_local` first.

#### [MODIFY] `DEVELOPER.md`
Cloud-only vs local OCR+embed install notes.

**Acceptance:** No Gemini key + Paddle + SentenceTransformers → searchable memories.

---

### Phase N — Docs Truth (1 day) `Priority: MEDIUM`

#### [MODIFY] `docs/PRODUCT.md`, `docs/PROJECT.md`
Delete “Review 1 / frontend only / no backend”. Point to `DEVELOPER.md` and this plan.

#### [MODIFY] `docs/STATUS.md`
Replace with a pointer to root `STATUS.md`.

#### [MODIFY] `STATUS.md`
- Remove duplicate unchecked Phase B items
- Phase C: **partial** (column + write path done; ANN search = Phase J)
- Phase E / H: match Correction_Plan
- List Phases I–N as pending

**Acceptance:** Docs do not contradict the running API.

---

## Priority if you only have 2 weeks

| Week | Phases | Outcome |
|---|---|---|
| Week 1 | J + L | Search/chat scale and tell the truth; Insights honest |
| Week 2 | K | Graph is the product |
| After | I, M, N | Aliases, offline OCR, docs |

Skip: auth, Redis/Celery, OS screenshot hooks, model training.

---

## Verification (remaining work)

```bash
cd backend && pytest tests/ -v
pytest tests/test_pgvector_search.py    # Phase J
pytest tests/test_relationships_v2.py   # Phase K
```

Manual:

1. Empty DB → Search/Memories/Timeline/Connections all empty (no synthetic hits).
2. Insights never shows 98.2% unless that is the real average.
3. Upload / seed → search “CUDA error” uses ANN (first page, not a full scan).
4. Chat “what was I doing with CUDA?” cites rows via `memory.embedding`.
5. “Internship” + January uses `captured_at`.
6. Connections force graph: internship cluster + domain/semantic edges.
7. Optional: stop Gemini, confirm local embed + Paddle path.

---

## Target architecture (after I–N)

```
Upload / Folder Watch
        ↓
   Ingest (hash dedup + optional rate limit)
        ↓
   Pipeline queue
   ├── Preprocess (EXIF → captured_at)
   ├── OCR (PaddleOCR → LLM vision → explicit empty/fail)
   ├── AI extract (title, tags, entities, app, domain) + entity normalize
   ├── Embed (local ST / Gemini → memories.embedding)
   └── Relationships (entity + tag + semantic≥0.65 + temporal + domain)
        ↓
   PostgreSQL + pgvector HNSW
   ├── memories.embedding
   ├── relationships
   ├── projects / memory_projects
   ├── stories
   └── entities (normalized)
        ↓
   Search: ANN top-K + FTS hybrid (no full-table Python scan)
   Chat: RAG on the same vectors
   Connections: force graph (memory / entity / project / domain)
   Insights: API metrics only
```

Completed Phase A–H checklists: [`Correction_Plan.md`](Correction_Plan.md).
