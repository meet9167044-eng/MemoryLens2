"""
POST /api/v1/chat — Phase E: RAG Conversational Memory Assistant

Flow:
    1. Embed the user's question (Gemini text-embedding-004).
    2. Find top-5 most relevant Memory rows (cosine similarity on stored embeddings).
    3. Build a Gemini LLM prompt with memory context injected.
    4. Return the grounded answer with memory citations.

Falls back to a helpful "no data" message when:
    - No memories have been uploaded yet.
    - No Gemini API key is configured.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.memory import Memory
from app.services.db_search import _embed_query, retrieve_by_embedding

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User's question")
    session_id: Optional[str] = Field(default=None, description="Optional session ID for conversation tracking")
    context_memory_ids: Optional[List[str]] = Field(default=None, description="Explicit memory IDs (e.g. from search results) to ground the answer")


class Citation(BaseModel):
    memory_id: str
    title: str
    timestamp: str
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    memories_searched: int
    model_used: str


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _retrieve_top_memories(
    db: Session,
    query_vec: Optional[list],
    q: str,
    context_memory_ids: Optional[List[str]] = None,
    k: int = 5,
) -> List[Memory]:
    """Top-k memories via pgvector ANN on memory.embedding (not embedding_placeholder)."""
    pinned: List[Memory] = []
    if context_memory_ids:
        from sqlalchemy import cast, String
        pinned = db.query(Memory).filter(Memory.id.cast(String).in_(context_memory_ids)).all()

    pinned_ids = {str(m.id) for m in pinned}
    extra = retrieve_by_embedding(
        db,
        query_vec,
        q,
        k=max(k, 1),
        exclude_ids=pinned_ids,
    )
    combined = pinned + extra
    return combined[: max(k, len(pinned))]


def _build_context(memories: List[Memory]) -> str:
    """Build the memory context block to inject into the LLM prompt."""
    parts = []
    for i, m in enumerate(memories, 1):
        # Phase B: prefer captured_at (real screenshot time) over created_at (upload time)
        real_ts = m.captured_at or m.created_at
        ts = real_ts.strftime("%Y-%m-%d %H:%M") if real_ts else "unknown time"
        parts.append(
            f"[Memory {i}] — {ts}\n"
            f"Title: {m.title or 'Untitled'}\n"
            f"Summary: {m.summary or 'No summary'}\n"
            f"OCR Text: {(m.raw_ocr_text or '')[:400]}\n"
            f"Tags: {', '.join(m.tags or [])}\n"
        )
    return "\n---\n".join(parts)


def _extract_citations(memories: List[Memory]) -> List[Citation]:
    return [
        Citation(
            memory_id=str(m.id),
            title=m.title or "Untitled",
            # Phase B: prefer captured_at (real screenshot time) over created_at (upload time)
            timestamp=(m.captured_at or m.created_at).isoformat() if (m.captured_at or m.created_at) else "",
            snippet=(m.summary or m.raw_ocr_text or "")[:120],
        )
        for m in memories
    ]


_RAG_PROMPT_TEMPLATE = """\
You are MemoryLens Assistant, an AI that helps users recall information from their uploaded screenshots and digital memories.

Below are the most relevant memories retrieved for the user's question:

{context}

---

User's question: {question}

Instructions:
- Answer the question based ONLY on the provided memories above.
- Be concise and specific.
- Reference relevant memories using [Memory 1], [Memory 2] etc.
- If the memories don't contain enough information to answer, say so honestly.
- Do NOT make up information that isn't in the memories.
- Format your answer in clear, readable prose (not bullet points unless necessary).
"""


def _call_gemini_chat(question: str, context: str) -> tuple[str, str]:
    """Call Gemini to generate a grounded answer. Returns (answer, model_used)."""
    try:
        from app.config import settings
        from google import genai
        
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = _RAG_PROMPT_TEMPLATE.format(context=context, question=question)

        # Assuming gemini-3.6-flash from user's test, falling back to gemini-1.5-flash
        for model_name in ["gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text or "I couldn't generate a response.", model_name
            except Exception:
                continue

        return "I encountered an error generating a response. Please try again.", "none"
    except Exception as exc:
        logger.error("Gemini chat failed: %s", exc)
        return "An error occurred while processing your question.", "none"


def _call_groq_chat(question: str, context: str) -> tuple[str, str]:
    """Call Groq over the OpenAI-compatible endpoint and return (answer, model_used)."""
    try:
        from app.config import settings
        from openai import OpenAI

        client = OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.GROQ_BASE_URL)
        prompt = _RAG_PROMPT_TEMPLATE.format(context=context, question=question)

        resp = client.chat.completions.create(
            model=settings.GROQ_CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
            timeout=30,
        )
        answer = resp.choices[0].message.content or "I couldn't generate a response."
        return answer, settings.GROQ_CHAT_MODEL
    except Exception as exc:
        logger.error("Groq chat failed: %s", exc)
        return "An error occurred while processing your question.", "none"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a question about your memories (RAG)",
    description=(
        "Natural language Q&A over your uploaded memories. "
        "Retrieves the most relevant memories and uses Gemini to generate a grounded answer with citations."
    ),
)
def chat(
    body: ChatMessage,
    db: Session = Depends(get_db),
) -> ChatResponse:
    from app.config import settings

    total_memories = db.query(Memory).count()

    # No memories uploaded yet
    if total_memories == 0:
        return ChatResponse(
            answer=(
                "You haven't uploaded any memories yet! "
                "Go to the upload section to add screenshots, and I'll be able to answer questions about them."
            ),
            citations=[],
            memories_searched=0,
            model_used="none",
        )

    # No API key — keyword match only, no LLM answer
    if not settings.GEMINI_API_KEY and not settings.GROQ_API_KEY:
        top = _retrieve_top_memories(db, None, body.message, k=5)
        if not top:
            answer = "I couldn't find any memories related to your question."
        else:
            titles = ", ".join(f'"{m.title or "Untitled"}"' for m in top)
            answer = (
                f"I found {len(top)} potentially related memories: {titles}. "
                "Add a GEMINI_API_KEY or GROQ_API_KEY to your .env for AI-powered answers."
            )
        return ChatResponse(
            answer=answer,
            citations=_extract_citations(top),
            memories_searched=total_memories,
            model_used="keyword-only",
        )

    # Full RAG flow
    query_vec = _embed_query(body.message)
    # 3. Retrieve related memories (Semantic + Keyword + Pinned Context)
    top_memories = _retrieve_top_memories(db, query_vec, body.message, context_memory_ids=body.context_memory_ids, k=5)

    if not top_memories:
        return ChatResponse(
            answer="I couldn't find any memories related to your question.",
            citations=[],
            memories_searched=total_memories,
            model_used="none",
        )

    context = _build_context(top_memories)
    if settings.LLM_PROVIDER.lower() == "groq" and settings.GROQ_API_KEY:
        answer, model_used = _call_groq_chat(body.message, context)
    elif settings.GEMINI_API_KEY:
        answer, model_used = _call_gemini_chat(body.message, context)
    elif settings.GROQ_API_KEY:
        answer, model_used = _call_groq_chat(body.message, context)
    else:
        answer, model_used = "I encountered an error generating a response. Please try again.", "none"
    citations = _extract_citations(top_memories)

    return ChatResponse(
        answer=answer,
        citations=citations,
        memories_searched=total_memories,
        model_used=model_used,
    )
