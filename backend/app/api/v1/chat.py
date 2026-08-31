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

import json
import math
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.memory import Memory

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

def _cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _embed_query(q: str) -> Optional[list]:
    try:
        from app.config import settings
        if not settings.GEMINI_API_KEY:
            return None
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        result = genai.embed_content(
            model=f"models/{settings.EMBEDDING_MODEL}",
            content=q,
            task_type="RETRIEVAL_QUERY",
        )
        return result["embedding"]
    except Exception as exc:
        logger.warning("Query embedding failed: %s", exc)
        return None


def _retrieve_top_memories(db: Session, query_vec: Optional[list], q: str, context_memory_ids: Optional[List[str]] = None, k: int = 5) -> List[Memory]:
    """Retrieve top-k most relevant memories using vector similarity + keyword fallback, optionally pinning specific memories."""
    # 1. If explicit context is provided, fetch those first
    pinned = []
    if context_memory_ids:
        from sqlalchemy import cast, String
        pinned = db.query(Memory).filter(Memory.id.cast(String).in_(context_memory_ids)).all()
        # If we have enough pinned memories, we can just return them or supplement them
        
    # We still fetch others to supplement up to K
    memories = db.query(Memory).all()
    if not memories:
        return pinned
        
    pinned_ids = {str(m.id) for m in pinned}

    if query_vec:
        scored = []
        for m in memories:
            score = 0.0
            if m.embedding_placeholder:
                try:
                    stored = json.loads(m.embedding_placeholder)
                    if isinstance(stored, list) and stored:
                        score = _cosine(query_vec, stored)
                except (json.JSONDecodeError, TypeError):
                    pass
            # Keyword boost
            q_lower = q.lower()
            doc = f"{m.title or ''} {m.summary or ''} {m.raw_ocr_text or ''}".lower()
            if q_lower in doc:
                score += 0.3
            scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Exclude pinned to avoid duplicates, then combine
        extra = [m for _, m in scored if str(m.id) not in pinned_ids]
        return (pinned + extra)[:max(k, len(pinned))]
    else:
        # Keyword-only fallback
        q_lower = q.lower()
        scored = []
        for m in memories:
            doc = f"{m.title or ''} {m.summary or ''} {m.raw_ocr_text or ''}".lower()
            if q_lower in doc:
                scored.append(m)
        extra = [m for m in scored if str(m.id) not in pinned_ids]
        if not extra:
            extra = [m for m in memories if str(m.id) not in pinned_ids]
        return (pinned + extra)[:max(k, len(pinned))]


def _build_context(memories: List[Memory]) -> str:
    """Build the memory context block to inject into the LLM prompt."""
    parts = []
    for i, m in enumerate(memories, 1):
        ts = m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "unknown time"
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
            timestamp=m.created_at.isoformat() if m.created_at else "",
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
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold

        genai.configure(api_key=settings.GEMINI_API_KEY)

        safety = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        prompt = _RAG_PROMPT_TEMPLATE.format(context=context, question=question)

        for model_name in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content(
                    prompt,
                    safety_settings=safety,
                    generation_config={"temperature": 0.2, "max_output_tokens": 1024},
                    request_options={"timeout": 30},
                )
                return resp.text or "I couldn't generate a response.", model_name
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
