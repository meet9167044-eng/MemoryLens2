"""
LLM Extractor — Phase B
========================
Sends an uploaded image to a multimodal LLM (Gemini 1.5/2.0 Flash or GPT-4o-mini)
and returns structured extraction: title, summary, OCR text, entities, tags.

Provider priority:
    1. Gemini  — if GEMINI_API_KEY is set and LLM_PROVIDER == "gemini"
    2. OpenAI  — if OPENAI_API_KEY is set and LLM_PROVIDER == "openai"
    3. Stub    — always available; uses filename as title, everything else blank.

Design:
    - All providers return the same ExtractionResult dataclass.
    - The caller (pipeline.py) doesn't care which provider ran.
    - Timeout = 30s. On any exception the stub result is returned so the
      pipeline never fails due to an LLM outage.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Result schema
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ExtractedEntity:
    name: str
    type: str  # "technology" | "framework" | "tool" | "company" | "person" | "topic" | "other"


@dataclass
class ExtractionResult:
    title: str
    summary: str
    ocr_text: str
    app_detected: str
    source_type: str  # "desktop" | "browser" | "terminal" | "document" | "other"
    domain: str = ""  # Phase D: extracted website domain
    entities: List[ExtractedEntity] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are MemoryLens, an AI that analyses screenshots and extracts structured memory metadata.

Analyse the provided screenshot and return ONLY valid JSON matching this exact schema:
{
  "title": "<concise, specific title for what this screenshot shows>",
  "summary": "<2-3 sentence explanation of what the user was doing>",
  "ocr_text": "<verbatim text visible in the screenshot, newline-separated>",
  "app_detected": "<name of the application or website visible, e.g. VS Code, Chrome, Terminal>",
  "source_type": "<one of: desktop, browser, terminal, document, other>",
  "domain": "<if a browser/website is visible, the domain name e.g. github.com, stackoverflow.com — else empty string>",
  "entities": [
    {"name": "<entity name>", "type": "<technology|framework|tool|company|person|topic|other>"}
  ],
  "tags": ["<lowercase-hyphenated-tag>"],
  "confidence": <float 0.0-1.0 representing overall extraction confidence>
}

Rules:
- Return ONLY the JSON object, no markdown fences, no commentary.
- Extract every visible word for ocr_text (preserve code formatting with \\n).
- Include 3-8 meaningful tags.
- Include all visible technologies, tools, frameworks, companies as entities.
- If no text is visible, set ocr_text to "".
- For domain: only include the root domain (e.g. "github.com", not the full URL).
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_llm_json(raw: str, filename: str) -> ExtractionResult:
    """Parse the LLM JSON response into an ExtractionResult, with safe fallbacks."""
    # Strip markdown fences if LLM ignores the instruction
    cleaned = re.sub(r"^```(?:json)?\s*|```\s*$", "", raw.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON — using stub for %s", filename)
        return _stub_result(filename)

    entities = [
        ExtractedEntity(name=e.get("name", ""), type=e.get("type", "other"))
        for e in data.get("entities", [])
        if e.get("name")
    ]

    return ExtractionResult(
        title=data.get("title") or filename,
        summary=data.get("summary") or "",
        ocr_text=data.get("ocr_text") or "",
        app_detected=data.get("app_detected") or "Unknown",
        source_type=data.get("source_type") or "other",
        domain=data.get("domain") or "",
        entities=entities,
        tags=[str(t).lower() for t in data.get("tags", [])],
        confidence=float(data.get("confidence", 0.7)),
    )


def _stub_result(filename: str) -> ExtractionResult:
    """Minimal result used when no LLM is available."""
    name = filename.rsplit(".", 1)[0] if "." in filename else filename
    return ExtractionResult(
        title=name.replace("_", " ").replace("-", " ").title(),
        summary="",
        ocr_text="",
        app_detected="Unknown",
        source_type="other",
        entities=[],
        tags=["screenshot"],
        confidence=0.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Gemini provider
# ─────────────────────────────────────────────────────────────────────────────

def _extract_gemini(image_bytes: bytes, filename: str) -> ExtractionResult:
    """Call Google Gemini with the image and return structured output."""
    try:
        from google import genai
    except ImportError:
        logger.warning("google.genai not installed — using stub.")
        return _stub_result(filename)

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Use the new gemini models
    model_names = ["gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

    import PIL.Image
    import io as _io
    pil_img = PIL.Image.open(_io.BytesIO(image_bytes))

    last_exc = None
    for model_name in model_names:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[_SYSTEM_PROMPT, pil_img],
            )
            raw = response.text or ""
            return _parse_llm_json(raw, filename)
        except Exception as exc:
            last_exc = exc
            logger.debug("Gemini model %s failed: %s", model_name, exc)
            continue

    logger.error("All Gemini models failed for %s: %s", filename, last_exc)
    return _stub_result(filename)


# ─────────────────────────────────────────────────────────────────────────────
# Groq provider
# ─────────────────────────────────────────────────────────────────────────────

def _extract_groq(image_bytes: bytes, filename: str) -> ExtractionResult:
    """Call Groq via the OpenAI-compatible API and return structured output."""
    try:
        from openai import OpenAI
        import base64
    except ImportError:
        logger.warning("openai package not installed — using stub.")
        return _stub_result(filename)

    try:
        import base64
        b64 = base64.b64encode(image_bytes).decode()
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
        mime = f"image/{ext}" if ext in ("png", "jpeg", "jpg", "webp") else "image/png"

        client = OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.GROQ_BASE_URL)
        resp = client.chat.completions.create(
            model=settings.GROQ_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _SYSTEM_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ],
            max_tokens=2048,
            temperature=0.1,
            timeout=30,
        )
        raw = resp.choices[0].message.content or ""
        return _parse_llm_json(raw, filename)
    except Exception as exc:
        logger.error("Groq extraction failed for %s: %s", filename, exc)
        return _stub_result(filename)


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI provider
# ─────────────────────────────────────────────────────────────────────────────

def _extract_openai(image_bytes: bytes, filename: str) -> ExtractionResult:
    """Call OpenAI GPT-4o-mini with vision and return structured output."""
    try:
        import openai
        import base64
    except ImportError:
        logger.warning("openai not installed — using stub.")
        return _stub_result(filename)

    import base64
    b64 = base64.b64encode(image_bytes).decode()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    mime = f"image/{ext}" if ext in ("png", "jpeg", "jpg", "webp") else "image/png"

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _SYSTEM_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ],
            max_tokens=2048,
            temperature=0.1,
            timeout=30,
        )
        raw = resp.choices[0].message.content or ""
        return _parse_llm_json(raw, filename)
    except Exception as exc:
        logger.error("OpenAI extraction failed for %s: %s", filename, exc)
        return _stub_result(filename)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

class LLMExtractor:
    """
    Multimodal LLM extraction wrapper.

    Usage:
        extractor = LLMExtractor()
        result = extractor.extract(image_bytes, filename="screenshot.png")
    """

    def extract(self, image_bytes: bytes, filename: str = "upload.png") -> ExtractionResult:
        """
        Extract structured metadata from an image.
        Provider is chosen based on settings.LLM_PROVIDER and available API keys.
        Never raises — returns a stub result on any failure.
        """
        provider = settings.LLM_PROVIDER.lower()

        # Explicit provider precedence
        if provider == "groq" and settings.GROQ_API_KEY:
            logger.info("LLM extraction via Groq for %s", filename)
            return _extract_groq(image_bytes, filename)

        if provider == "gemini" and settings.GEMINI_API_KEY:
            logger.info("LLM extraction via Gemini for %s", filename)
            return _extract_gemini(image_bytes, filename)

        if provider == "openai" and settings.OPENAI_API_KEY:
            logger.info("LLM extraction via OpenAI for %s", filename)
            return _extract_openai(image_bytes, filename)

        # Auto-detect fallback order
        if settings.GEMINI_API_KEY:
            logger.info("Auto: LLM extraction via Gemini for %s", filename)
            return _extract_gemini(image_bytes, filename)

        if settings.GROQ_API_KEY:
            logger.info("Auto: LLM extraction via Groq for %s", filename)
            return _extract_groq(image_bytes, filename)

        if settings.OPENAI_API_KEY:
            logger.info("Auto: LLM extraction via OpenAI for %s", filename)
            return _extract_openai(image_bytes, filename)

        logger.warning("No LLM API key configured — using stub extractor for %s", filename)
        return _stub_result(filename)


# Module-level singleton
llm_extractor = LLMExtractor()
