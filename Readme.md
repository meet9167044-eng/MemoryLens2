<div align="center">

# 🔍 MemoryLens

### *Your screenshots remember everything. You just have to ask.*

**MemoryLens** is an AI-powered personal memory engine that turns screenshots into a searchable knowledge graph — letting you retrieve not just individual images, but the *people, projects, conversations, websites, and timelines* connected to them.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![pgvector](https://img.shields.io/badge/pgvector-HNSW-orange)](https://github.com/pgvector/pgvector)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

</div>

---

## What is MemoryLens?

> **"Find the CUDA error I got while training my ML model in January."**

Normal image search fails here. You don't remember the filename, the folder, or the exact words. MemoryLens finds it anyway — and shows you everything connected to it.

| Google Photos | MemoryLens |
|---|---|
| Find pictures | **Find the story behind your pictures** |
| Keyword / object search | Semantic natural language search |
| Isolated files | Knowledge graph of related memories |
| Creation date only | Original capture time from EXIF |
| No relationships | Semantic + temporal + domain + entity links |

---

## Quick Start

> ⚡ **5 commands to a running app**

```bash
# 1. Set up the backend
cd backend
pip install -r requirements.txt
cp .env.example .env    # then add your GROQ_API_KEY

# 2. Initialize the database
alembic upgrade head

# 3. Start the backend
uvicorn app.main:app --reload --port 8000

# 4. Start the frontend (new terminal, project root)
npm install && npm run dev

# 5. Seed demo data (optional but recommended)
python scripts/seed_demo.py
```

Open **http://localhost:5173** → upload a screenshot → watch the magic.

---

## How It Works

```
📸 Upload Screenshot
        │
        ▼
┌────────────────────────────────────────────────────────┐
│                   Async Pipeline                        │
│  ┌─────────────┐  ┌─────────┐  ┌────────────────────┐ │
│  │ Preprocessing│→ │   OCR   │→ │   AI Extraction    │ │
│  │ EXIF → time │  │ PaddleOCR│  │ Llama 3.2 Vision   │ │
│  │             │  │ / LLM   │  │ title, entities,   │ │
│  └─────────────┘  └─────────┘  │ tags, app, domain  │ │
│                                 └────────────────────┘ │
│  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │    Embedding      │→ │    Relationship Engine    │   │
│  │ SentenceTransform │  │ semantic + temporal +     │   │
│  │ ers (local 768d)  │  │ domain + shared-entity   │   │
│  └──────────────────┘  └──────────────────────────┘   │
└────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│   PostgreSQL + pgvector       │
│   ├── screenshots             │
│   ├── memories + embeddings   │
│   ├── entities (normalized)   │
│   ├── relationships (4 types) │
│   └── stories (auto-grouped)  │
└───────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│              React Frontend              │
│  Search  │  Graph  │  Chat  │  Timeline  │
└──────────────────────────────────────────┘
```

---

## Features

### 🔍 Semantic Search
- **Hybrid scoring**: 60% pgvector cosine (768-dim HNSW index) + 40% PostgreSQL full-text
- **Natural language queries**: "CUDA error in January" or "internship application screenshots"
- **Faceted filters**: filter by app, date range, content type

### 🕸️ Knowledge Graph
- **4 relationship types**: Semantic (embedding similarity ≥ 0.65) · Temporal (within 2h window) · Domain (same website) · Shared entity
- **Interactive force-directed graph** — click any node to explore its neighborhood
- **Auto-grouped Stories** — temporal+semantic clusters of related screenshots
- **Project detection** — heuristic clustering by entity co-occurrence

### 💬 Contextual RAG Chat
- Ask questions about your memories in plain English
- Answers cite the actual screenshots used as context
- Follow-up queries use previous results as seeds

### 📅 Timeline
- 12-week GitHub-style activity heatmap
- Click any day to see all screenshots from that session
- Timestamps from EXIF metadata (not upload time)

### ⚙️ Auto-Ingestion
- Folder watcher daemon — drop screenshots in a folder, they're automatically ingested
- Bulk import via `/api/v1/ingest/bulk`
- SHA-256 deduplication — never processes the same file twice

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI 0.109 + Python 3.11 |
| **Database** | PostgreSQL 16 + pgvector (HNSW index) |
| **Embeddings** | SentenceTransformers `all-mpnet-base-v2` (local, offline) |
| **Vision LLM** | Groq `llama-3.2-11b-vision-preview` (free tier) |
| **Chat LLM** | Groq `llama-3.1-8b-instant` |
| **Migrations** | Alembic |
| **Frontend** | React 18 + TypeScript + Vite |
| **Graph UI** | react-force-graph |
| **Queue** | In-process `PriorityQueue` (no Redis needed) |

---

## Environment Variables

Create `backend/.env` (see `backend/.env.example`):

```env
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/memorylens_db
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...          # Free at console.groq.com
GROQ_VISION_MODEL=llama-3.2-11b-vision-preview
GROQ_CHAT_MODEL=llama-3.1-8b-instant
EMBEDDING_PROVIDER=local      # No API key needed
```

---

## Project Structure

```
MemoryLens/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # FastAPI route handlers
│   │   ├── core/            # Local embedder, config
│   │   ├── jobs/            # Async pipeline + queue
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── processing/      # OCR, relationship engine
│   │   ├── services/        # LLM extractor, search, storage
│   │   └── schemas/         # Pydantic request/response schemas
│   ├── migrations/          # Alembic migration scripts
│   └── tests/               # pytest test suite
├── src/                     # React + TypeScript frontend
│   ├── pages/               # Search, Graph, Chat, Timeline, Insights
│   └── components/          # Shared UI components
├── scripts/
│   ├── seed_demo.py         # Populate 50 realistic demo memories
│   └── demo_flow.md         # Step-by-step demo walkthrough script
├── DEVELOPER.md             # Full local setup guide
└── README.md
```

---

## Demo

Run the demo seeder to get 50 realistic memories across 5 storylines:

```bash
cd backend
python ../scripts/seed_demo.py
```

**Storylines included:**
- 🧠 **ML / CUDA Debugging** — 12 memories across VS Code, Terminal, Stack Overflow
- 💼 **Google Internship Application** — 12 memories across LinkedIn, Gmail, LeetCode
- 🐙 **GitHub Code Review** — 8 memories of a PR review cycle
- ⚙️ **System Setup** — 10 memories of the full project setup
- 📚 **Study Session** — 8 memories of deep learning research

Then follow the [`scripts/demo_flow.md`](scripts/demo_flow.md) walkthrough for a 10-minute guided demo.

---

## API Reference

```
POST   /api/v1/ingest              Upload a screenshot
POST   /api/v1/ingest/bulk         Bulk import from folder path
GET    /api/v1/memories            List all memories (paginated)
GET    /api/v1/memories/{id}       Get single memory
GET    /api/v1/memories/{id}/related  Related screenshots
GET    /api/v1/search?q=...        Hybrid semantic search
GET    /api/v1/connections         Knowledge graph edges
POST   /api/v1/chat                RAG chat
GET    /api/v1/insights            Aggregated stats
POST   /api/v1/watch/start         Start folder watcher
```

Interactive docs: **http://localhost:8000/docs**

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**Built with ❤️ by [Meet Jain](https://github.com/meet9167044)**

*"A screenshot isn't an isolated image. It's an event in your digital life."*

</div>
