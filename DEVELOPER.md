# MemoryLens — Developer Guide

> This is the canonical "how to run MemoryLens locally" document. 
> If something doesn't work, check here first.

---

## Prerequisites

| Tool | Required Version | Install |
|------|-----------------|---------|
| Python | 3.10+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| PostgreSQL | 14+ | [postgresql.org](https://postgresql.org) |
| Git | any | [git-scm.com](https://git-scm.com) |

---

## First-Time Setup

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd MemoryLens
```

### 2. Create the PostgreSQL database
```sql
-- In psql:
CREATE DATABASE memorylens_db;
```

### 3. Configure environment variables
```bash
cd backend
copy .env.example .env   # Windows
# then edit .env with your values (see table below)
```

### 4. Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 5. Run database migrations
```bash
cd backend
alembic upgrade head
```

### 6. Start the backend server
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
The API will be live at http://localhost:8000  
Interactive docs at http://localhost:8000/docs

### 7. Install frontend dependencies
```bash
# In a new terminal, from the project root:
npm install
```

### 8. Start the frontend dev server
```bash
npm run dev
```
The app will open at http://localhost:5173

---

## Environment Variables (`backend/.env`)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string | `postgresql+psycopg2://postgres:password@localhost:5432/memorylens_db` |
| `LLM_PROVIDER` | ✅ Yes | Which LLM to use for extraction | `groq` (recommended), `gemini`, `openai` |
| `GROQ_API_KEY` | If using Groq | API key from console.groq.com | `gsk_...` |
| `GROQ_VISION_MODEL` | If using Groq | Groq vision model name | `llama-3.2-11b-vision-preview` |
| `GROQ_CHAT_MODEL` | If using Groq | Groq chat model name | `llama-3.1-8b-instant` |
| `GEMINI_API_KEY` | If using Gemini | API key from Google AI Studio | `AIza...` |
| `OPENAI_API_KEY` | If using OpenAI | API key from platform.openai.com | `sk-...` |
| `EMBEDDING_PROVIDER` | No | Embedding backend | `local` (no key), `gemini` |
| `EMBEDDING_MODEL` | No | Model name for embeddings | `text-embedding-004` |
| `DATASET_STORAGE_PATH` | No | Where to store uploaded screenshots | `./data/dataset` |

---

## Getting a Free Groq API Key (Recommended)

Groq is free and provides fast vision+chat inference:

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (free)
3. Go to **API Keys** → **Create API Key**
4. Copy the key into `backend/.env` as `GROQ_API_KEY`
5. Set `LLM_PROVIDER=groq`
6. Set `GROQ_VISION_MODEL=llama-3.2-11b-vision-preview`
7. Set `GROQ_CHAT_MODEL=llama-3.1-8b-instant`

---

## Offline / Local Architecture

MemoryLens supports a fully offline, air-gapped configuration without needing Groq, Gemini, or OpenAI API keys.

To run completely locally:
1. Set `EMBEDDING_PROVIDER=local` in your `.env`. This forces the pipeline to use local `sentence-transformers` for vector generation.
2. Ensure you have installed the optional OCR packages: `pip install paddleocr paddlepaddle` (if these are not installed, the pipeline will just gracefully skip OCR).
   > [!WARNING]
   > Windows Users: The default PaddlePaddle binaries might conflict with `oneDNN`. The app gracefully catches this and logs a warning, falling back to LLM-vision OCR. But if you want PaddleOCR locally, you must follow official Paddle docs for Windows CPU installs.
3. Keep `LLM_PROVIDER` unset or set it to `stub` if you have no local LLM setup. (If you want local extraction, you can hook the pipeline to a local Ollama server).

---

## Common Errors

### `ModuleNotFoundError: No module named 'app'`
You must run the backend from the `backend/` folder, not the root:
```bash
cd backend
uvicorn app.main:app --reload
```

### `FATAL: database "memorylens_db" does not exist`
Create the DB first:
```sql
-- in psql:
CREATE DATABASE memorylens_db;
```
Then run `alembic upgrade head`.

### `alembic.util.exc.CommandError: Can't locate revision`
Run a full migration reset:
```bash
alembic downgrade base
alembic upgrade head
```

### Screenshots upload but show no title/tags/summary
This means LLM extraction failed. Check:
1. Is `GROQ_API_KEY` (or another key) set in `backend/.env`?
2. Is `LLM_PROVIDER` set correctly (e.g., `groq`)?
3. Is `GROQ_VISION_MODEL=llama-3.2-11b-vision-preview` (not `openai/gpt-oss-20b`)?
4. Check backend logs for `LLM extraction via...` messages.

### `CORS error` in the browser
Make sure `CORS_ORIGINS` in `.env` includes your frontend port (e.g., `http://localhost:5173`).

---

## Project Structure

```
MemoryLens/
├── backend/              ← FastAPI backend
│   ├── app/
│   │   ├── api/v1/       ← API route handlers
│   │   ├── core/         ← Embeddings, config
│   │   ├── db/           ← SQLAlchemy session + base
│   │   ├── jobs/         ← Background pipeline
│   │   ├── models/       ← SQLAlchemy ORM models
│   │   ├── processing/   ← OCR, relationship engine
│   │   ├── schemas/      ← Pydantic request/response schemas
│   │   └── services/     ← LLM extractor, search, storage
│   ├── migrations/       ← Alembic migration scripts
│   ├── tests/            ← Pytest test suite
│   ├── alembic.ini
│   └── requirements.txt
├── src/                  ← React + TypeScript frontend
│   ├── pages/            ← Page components (each in its own folder)
│   ├── components/       ← Shared UI components
│   ├── services/         ← API client functions
│   └── types/            ← TypeScript type definitions
├── scripts/              ← Utility scripts
├── DEVELOPER.md          ← This file
└── README.md             ← Project overview
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

To run a specific test file:
```bash
pytest tests/test_search.py -v
```
