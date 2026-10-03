"""Data extraction and duplicate detection services with zero-token local processing."""

import json
import time
import re
import logging
from difflib import SequenceMatcher

def _clean_json_syntax(text: str) -> str:
    """Removes trailing commas and normalizes JSON text prior to parsing."""
    # Strip trailing commas before closing braces/brackets
    cleaned = re.sub(r",\s*([\]}])", r"\1", text)
    return cleaned

def fast_extract(raw: str, model=None) -> list:
    """Parses structured JSON articles locally without token consumption, falling back to LLM if needed."""
    if not raw or not isinstance(raw, str):
        return []

    text = raw.strip()

    # 1. Attempt direct JSON parsing
    try:
        data = json.loads(text)
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception:
        pass

    # 2. Attempt parsing after sanitizing trailing commas
    try:
        data = json.loads(_clean_json_syntax(text))
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception:
        pass

    # 3. Extract JSON content enclosed within markdown code fences
    fence_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence_match:
        fence_content = fence_match.group(1).strip()
        try:
            data = json.loads(fence_content)
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            try:
                data = json.loads(_clean_json_syntax(fence_content))
                if isinstance(data, list) and len(data) > 0:
                    return data
            except Exception:
                pass

    # 4. Extract bracketed array payload via balanced bracket or regex
    array_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if array_match:
        array_content = array_match.group(0).strip()
        try:
            data = json.loads(array_content)
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            try:
                data = json.loads(_clean_json_syntax(array_content))
                if isinstance(data, list) and len(data) > 0:
                    return data
            except Exception:
                pass

    # 5. Fallback to Gemini extraction if local parsing cannot parse malformed text
    logging.info("[Extraction] Local parser encountered malformed output; invoking fallback LLM extractor.")
    return extract_with_llm(raw, model)

def extract_with_llm(raw: str, model=None) -> list:
    """Fallback LLM extractor for malformed agent outputs, self-initializing Gemini if model is None."""
    if model is None:
        try:
            import google.generativeai as genai
            from config.model_pool import get_active_model, get_active_key
            active_model = get_active_model()
            active_key = get_active_key()
            if active_key:
                genai.configure(api_key=active_key)
                model = genai.GenerativeModel(active_model)
        except Exception as init_err:
            logging.error(f"[Extraction] Failed to auto-initialize fallback Gemini model: {init_err}")
            return []

    if not model:
        return []

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
        parsed = json.loads(response.text)
        return parsed if isinstance(parsed, list) else []
    except Exception as e:
        logging.error(f"[Extraction] Fallback LLM extraction failed: {e}")
        return []

def local_detect_duplicates(posts: list, model=None, similarity_threshold: float = 0.75) -> list:
    """Detects duplicate articles locally, returning duplicate ids while safely preserving original records."""
    if not posts or len(posts) < 2:
        return []

    duplicate_ids = []
    seen = []

    for post in posts:
        post_id = post.get("id")
        mongo_id = post.get("_id")
        title = post.get("title", "").strip().lower()

        if not post_id or not title:
            continue

        is_dup = False
        for seen_doc in seen:
            seen_id = seen_doc.get("id")
            seen_title = seen_doc.get("title")

            if post_id == seen_id:
                is_dup = True
                break

            ratio = SequenceMatcher(None, title, seen_title).ratio()
            if ratio >= similarity_threshold:
                is_dup = True
                logging.info(
                    f"[Deduplication] Duplicate detected locally: '{post.get('title')}' is {ratio:.0%} similar to existing post."
                )
                break

        if is_dup:
            # Mark the duplicate record for removal (preserving the first encountered record)
            duplicate_ids.append(mongo_id if mongo_id else post_id)
        else:
            seen.append({"id": post_id, "title": title, "_id": mongo_id})

    return duplicate_ids

def detect_duplicates(posts: list, model=None) -> list:
    """Entrypoint for article duplicate detection."""
    return local_detect_duplicates(posts, model)
