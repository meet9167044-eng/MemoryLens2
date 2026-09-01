# MemoryLens Project Status

## Phase A — Codebase Cleanup ✅ DONE
- [x] Fixed Groq vision model (`llama-3.2-11b-vision-preview`) — root cause of missing tags/summaries
- [x] Fixed Groq chat model (`llama-3.1-8b-instant`)
- [x] Deleted dead backend stub (`backend/main.py`)
- [x] Deleted dead flat frontend pages
- [x] Created `DEVELOPER.md`
- [x] Upgraded Insights API with real stats
- [x] Added `file_hash` column + deduplication at ingest
- [x] Fixed `file_size_bytes` from `String` to `Integer`
- [x] DB migration applied: `2c5f3091dea7`

## Phase B — Timestamps & App Detection ✅ DONE
- [x] Added `app_detected`, `captured_at`, `domain` columns to `Memory` model
- [x] DB migration applied: `2c766c3a59a7`
- [x] Pipeline `_preprocess()` extracts `captured_at` from EXIF → filename pattern → mtime
- [x] Pipeline `_ai_extraction()` persists `app_detected` from LLM result
- [x] Search results use `app_detected` (not hardcoded "Unknown") and `captured_at` (not upload time)
- [x] Memories API sorts by `captured_at` desc for correct chronological ordering
- [x] Frontend `InsightStats` type updated with new fields

## Phase C — Real Vector Search 🟡 PARTIAL (column+HNSW yes, ANN search no)
## Phase D — Knowledge Graph Engine ✅ DONE
- [x] Semantic relationships: `_score_semantic()` using pgvector cosine similarity
- [x] Temporal relationships: `_score_temporal()` with 2-hour decay window on `captured_at`
- [x] Project auto-detector: `project_detector.py` (tags / domain / entity heuristics)
- [x] Domain linking: LLM prompt extended, `_score_domain()` added, `domain` persisted in pipeline
- [x] Story grouping: `story_builder.py` groups sessions by 30-min idle gap
- [x] Graph UI: Connections page upgraded with Knowledge Graph / Stories / Projects tabs
- [x] DB migration applied: `30e8c0b71561` (TEMPORAL + DOMAIN enum values)

## Phase E — Auto-Ingestion ⬜ PENDING
## Phase F — Scalability ✅ DONE
- [x] Background Pipeline Queue (`PriorityQueue` with fixed worker pool)
- [x] O(n²) Relationship Optimization (Candidate pre-fetching via exact/overlap filtering and pgvector)
- [x] File hash deduplication at ingest

## Phase G — UX Polish ✅ DONE
- [x] NL Query Parsing using Gemini API
- [x] Search Facets for Apps and Dates
- [x] Related Screenshots right-sidebar layout
- [x] Timeline 12-week Calendar Heatmap
- [x] Contextual Chat (search results passed to chat)

## Phase H — Demo Preparation ⬜ PENDING
## Phase I — FTS, Rate Limits, Search Edge Cases ✅ DONE
## Phase J — Strict Clustering & ANN Search ✅ DONE
## Phase K — Robust Graph Construction ✅ DONE
## Phase L — Honest UX ✅ DONE
## Phase M — Local OCR & Offline Path ✅ DONE
## Phase N — Docs Truth ✅ DONE
