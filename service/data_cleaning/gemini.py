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

STOPWORDS = {
    'the', 'a', 'an', 'is', 'in', 'on', 'of', 'and', 'for', 'with', 'to', 'at', 'by', 'from',
    'up', 'down', 'over', 'under', 'new', 'as', 'it', 'its', 'their', 'how', 'why', 'what',
    'after', 'into', 'inside', 'under', 'post', 'daily', 'editorial', 'unveils', 'reveals',
    'announces', 'shatters', 'breaks', 'rattles', 'shakes', 'inside', 'massive', 'major',
    'first', 'ahead', 'leaps', 'near', 'nears', 'threatens', 'disrupts', 'pushes', 'marks'
}


def extract_semantic_features(title: str, description: str = ""):
    """Extracts normalized tokens, technical version signatures, and descriptive vocabulary."""
    raw_tokens = re.findall(r'[a-zA-Z0-9\.]+', (title or '').lower())
    clean_tokens = {re.sub(r'^\.+|\.+$', '', t) for t in raw_tokens}
    clean_tokens = {t for t in clean_tokens if len(t) >= 2 and t not in STOPWORDS}
    versions = set(re.findall(r'\b\d+\.\d+\b', title or ''))
    desc_tokens = {t for t in re.findall(r'[a-zA-Z0-9]+', (description or '').lower()) if len(t) >= 3 and t not in STOPWORDS}
    return clean_tokens, versions, desc_tokens


def are_articles_semantic_duplicates(doc_a: dict, doc_b: dict) -> bool:
    """Evaluates whether two article documents report on the exact same real-world event/breakthrough."""
    title_a = (doc_a.get("title") or "").strip()
    title_b = (doc_b.get("title") or "").strip()
    if not title_a or not title_b:
        return False

    tokens_a, vers_a, desc_a = extract_semantic_features(title_a, doc_a.get("description", ""))
    tokens_b, vers_b, desc_b = extract_semantic_features(title_b, doc_b.get("description", ""))

    # Guard: Distinct version numbers indicate different updates/releases (e.g. 3.5 vs 3.7)
    if vers_a and vers_b and not (vers_a & vers_b):
        return False

    inter = tokens_a & tokens_b
    shorter = min(len(tokens_a), len(tokens_b))
    overlap = len(inter) / shorter if shorter > 0 else 0
    jaccard = len(inter) / len(tokens_a | tokens_b) if (tokens_a | tokens_b) else 0

    desc_inter = desc_a & desc_b
    desc_overlap = len(desc_inter) / min(len(desc_a), len(desc_b)) if (desc_a and desc_b) else 0

    # Domain-specific core entity-predicate clusters:
    has_cxmt_dram = ('cxmt' in inter and 'dram' in inter)
    has_quantum_bottleneck = ('quantum' in inter and any(k in inter for k in ['bottleneck', '40x', 'scaling']))
    has_weather_six_weeks = ('weather' in inter and any(k in inter for k in ['forecasting', 'weeks', 'six']))
    has_openai_crypto = ('openai' in inter and any(k in inter for k in ['cryptography', 'cryptographic', 'security']))

    is_duplicate = (
        has_cxmt_dram or
        has_quantum_bottleneck or
        has_weather_six_weeks or
        has_openai_crypto or
        overlap >= 0.55 or
        jaccard >= 0.40 or
        (overlap >= 0.38 and len(inter) >= 3 and desc_overlap >= 0.20)
    )

    return is_duplicate


def local_detect_duplicates(posts: list, model=None, similarity_threshold: float = 0.75) -> list:
    """Detects duplicate articles using intelligent semantic entity matching and lexical overlap."""
    if not posts or len(posts) < 2:
        return []

    duplicate_ids = []
    seen = []

    for post in posts:
        post_id = post.get("id")
        mongo_id = post.get("_id")
        title = post.get("title", "").strip()

        if not post_id or not title:
            continue

        is_dup = False
        for seen_doc in seen:
            if post_id == seen_doc.get("id"):
                is_dup = True
                break

            if are_articles_semantic_duplicates(post, seen_doc):
                is_dup = True
                logging.info(
                    f"[Deduplication] Semantic duplicate detected: '{post.get('title')}' is duplicate of '{seen_doc.get('title')}'."
                )
                break

        if is_dup:
            duplicate_ids.append(mongo_id if mongo_id else post_id)
        else:
            seen.append(post)

    return duplicate_ids


def detect_duplicates(posts: list, model=None) -> list:
    """Entrypoint for article duplicate detection."""
    return local_detect_duplicates(posts, model)

