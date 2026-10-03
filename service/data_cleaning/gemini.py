"""Data extraction and duplicate detection services with zero-token local processing."""

import json
import time
import re
import logging
from difflib import SequenceMatcher

def fast_extract(raw: str, model=None) -> list:
    """Parses structured JSON articles locally without token consumption, falling back to LLM if needed."""
    if not raw or not isinstance(raw, str):
        return []

    text = raw.strip()

    # Attempt direct JSON parsing
    try:
        data = json.loads(text)
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception:
        pass

    # Extract JSON content enclosed within markdown code fences
    fence_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence_match:
        try:
            data = json.loads(fence_match.group(1))
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            pass

    # Extract bracketed array payload via regex
    array_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if array_match:
        try:
            data = json.loads(array_match.group(0))
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            pass

    # Trigger fallback LLM extraction only when all deterministic parsers fail
    if model:
        logging.info("[Extraction] Local parser encountered non-JSON output; invoking fallback LLM extractor.")
        return extract_with_llm(raw, model)

    return []

def extract_with_llm(raw: str, model) -> list:
    """Fallback LLM extractor for malformed agent outputs."""
    prompt = f"""
        Extract news/article data from the raw text into a valid JSON array:
        [
          {{
            "id": "string",
            "category": ["string","string"],
            "title": "string",
            "description": "string",
            "content": "string",
            "image_prompt": "string"
          }}
        ]
        Never include markdown code blocks or text outside JSON.
        Raw Input:
        {raw}
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except Exception as e:
        logging.error(f"[Extraction] Fallback LLM extraction failed: {e}")
        return []

def local_detect_duplicates(posts: list, model=None, similarity_threshold: float = 0.75) -> list:
    """Detects duplicate articles locally using identifier matching and title similarity ratios."""
    if not posts or len(posts) < 2:
        return []

    duplicates = set()
    seen = []

    for post in posts:
        post_id = post.get("id")
        title = post.get("title", "").strip().lower()

        if not post_id or not title:
            continue

        is_dup = False
        for seen_id, seen_title in seen:
            if post_id == seen_id:
                is_dup = True
                break

            ratio = SequenceMatcher(None, title, seen_title).ratio()
            if ratio >= similarity_threshold:
                is_dup = True
                logging.info(f"[Deduplication] Duplicate detected locally: '{post.get('title')}' is {ratio:.0%} similar to existing post.")
                break

        if is_dup:
            duplicates.add(post_id)
        else:
            seen.append((post_id, title))

    return list(duplicates)

def detect_duplicates(posts: list, model=None) -> list:
    """Entrypoint for article duplicate detection."""
    return local_detect_duplicates(posts, model)
