"""
MemoryLens FastAPI application entry point.

Routers registered:
    GET  /api/v1/health              -- health check
    POST /api/v1/ingest              -- file upload + background pipeline
    POST /api/v1/ingest/bulk         -- bulk file upload (Phase E)
    GET  /api/v1/ingest/{id}         -- pipeline status
    GET  /api/v1/memories            -- list all memories
    GET  /api/v1/memories/{id}       -- memory detail
    GET  /api/v1/search              -- hybrid keyword + vector search (GET)
    POST /api/v1/search/hybrid       -- hybrid search (POST body)
    GET  /api/v1/timeline            -- chronological grouped feed
    GET  /api/v1/connections         -- graph nodes + edges + stories + projects
    POST /api/v1/chat                -- RAG conversational assistant
    GET  /api/v1/screenshots/{id}/image -- serve raw image bytes
    GET  /api/v1/watch               -- folder watcher status (Phase E)
    POST /api/v1/watch/start         -- start folder watcher (Phase E)
    POST /api/v1/watch/stop          -- stop folder watcher (Phase E)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import health, search, memories, timeline, insights
from app.api.v1.ingest import router as ingest_router
from app.api.v1.connections import router as connections_router
from app.api.v1.chat import router as chat_router
from app.api.v1.watch import router as watch_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="MemoryLens backend API — multimodal AI memory search.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow the Vite frontend to call the API during development
# ---------------------------------------------------------------------------
cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if settings.CORS_ORIGINS:
    for o in settings.CORS_ORIGINS:
        s = str(o).rstrip("/")
        if s not in cors_origins:
            cors_origins.append(s)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix=settings.API_V1_STR, tags=["health"])
app.include_router(ingest_router, tags=["ingestion"])           # ingest router has its own /api/v1 prefix
app.include_router(search.router, prefix=settings.API_V1_STR, tags=["search"])
app.include_router(memories.router, prefix=settings.API_V1_STR)
app.include_router(timeline.router, prefix=settings.API_V1_STR)
app.include_router(connections_router, prefix=settings.API_V1_STR, tags=["connections"])
app.include_router(chat_router, prefix=settings.API_V1_STR, tags=["chat"])
app.include_router(insights.router, prefix=settings.API_V1_STR, tags=["insights"])
app.include_router(watch_router, tags=["watch"])               # watch router has its own /api/v1 prefix
