"""
Natural Language Query Parser (Phase G)
========================================
Extracts intent and implicit filters (dates, apps, entities, tags) from a search query using Gemini.
Returns structured JSON to augment the database search filters.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


def parse_search_query(query: str) -> Dict[str, Any]:
    """
    Given a search query, uses Gemini to extract filters.
    If parsing fails or Gemini is unavailable, returns a default empty structure.
    
    Returns:
        {
            "query": "The core semantic search query after stripping filters",
            "app": "optional app name",
            "date_from": "YYYY-MM-DD",
            "date_to": "YYYY-MM-DD",
            "tags": ["tag1", "tag2"],
        }
    """
    default_res = {
        "query": query,
        "app": None,
        "date_from": None,
        "date_to": None,
        "tags": []
    }

    if not settings.GEMINI_API_KEY:
        return default_res

    try:
        import google.generativeai as genai
        from google.generativeai.types import generation_types

        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Use a fast model for parsing
        model = genai.GenerativeModel(
            f"models/{settings.LLM_MODEL}",
            generation_config={"response_mime_type": "application/json"}
        )

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        prompt = f"""
You are a search query parser for a personal memory assistant.
Today's date is {now_str}.
Given the user's search query, extract implicit filters and return the rest of the text as the semantic query.

Extract these fields if present:
- app: The name of an application (e.g., "VS Code", "Chrome", "Slack").
- date_from: ISO 8601 date string (YYYY-MM-DD). Parse relative terms like "last week", "yesterday", "in January 2024".
- date_to: ISO 8601 date string. If the query implies a single day (like "yesterday"), date_from and date_to should be the same.
- tags: Array of specific keywords/tags mentioned (e.g., "error", "invoice", "meeting").
- query: The remaining part of the text that describes the actual content the user is looking for, stripped of the filter words.

If a field is not present, return null for it (or empty array for tags).

User Query: "{query}"

Respond ONLY with valid JSON matching this schema:
{{
  "query": string,
  "app": string | null,
  "date_from": string | null,
  "date_to": string | null,
  "tags": [string]
}}
"""
        response = model.generate_content(prompt)
        text = response.text
        
        if text.startswith("```json"):
            text = text[7:-3]
            
        res = json.loads(text.strip())
        
        # Merge with defaults to ensure all keys exist
        return {**default_res, **res}
        
    except Exception as exc:
        logger.warning("NL Query parsing failed: %s", exc)
        return default_res