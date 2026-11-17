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

FINANCIAL_SYNONYMS = {
    'fed': 'federal reserve',
    'feds': 'federal reserve',
    'powell': 'federal reserve',
    'cryptocurrency': 'crypto',
    'cryptos': 'crypto',
    'lawsuits': 'lawsuit',
    'suing': 'lawsuit',
    'sues': 'lawsuit',
    'sued': 'lawsuit',
    'regulators': 'regulation',
    'regulatory': 'regulation',
    'plunges': 'drop',
    'plunge': 'drop',
    'slips': 'drop',
    'slip': 'drop',
    'erases': 'drop',
    'erase': 'drop',
    'wipes': 'drop',
    'wipeout': 'drop',
    'sheds': 'drop',
    'shed': 'drop',
    'plummet': 'drop',
    'plummeting': 'drop',
    'rout': 'downturn',
    'selloff': 'downturn',
    'sell-off': 'downturn',
    'slump': 'downturn',
    'halts': 'halt',
    'pauses': 'halt',
    'pause': 'halt',
    'halted': 'halt',
}

KNOWN_ENTITIES = {
    # Jurisdictions & Countries
    'armenia', 'canada', 'south africa', 'us', 'usa', 'united states', 'uk', 'britain',
    'germany', 'china', 'japan', 'france', 'europe', 'eu', 'silicon valley',
    # Key Technology & Financial Institutions
    'nvidia', 'apple', 'google', 'microsoft', 'anthropic', 'openai', 'spacex', 'tesla',
    'deutsche bank', 'federal reserve', 'sec', 'binance', 'coinbase', 'ftx',
    # Key Figures
    'jensen huang', 'ramaphosa', 'elon musk', 'cathie wood', 'bengio', 'hinton', 'altman',
    # Asset Classes & Financial Instruments
    'bitcoin', 'ethereum', 'solana', 'xrp', 'bnb', 'treasury', 'bunds', 'yields', 'etf'
}


def extract_quant_metrics(text: str) -> set:
    """Extracts normalized quantifiable financial figures, percentages, and metrics."""
    words = (text or '').lower().replace('$', ' ').replace('€', ' ').replace('£', ' ').replace(',', '').split()
    metrics = set()
    for i, w in enumerate(words):
        digits = ''.join(c for c in w if c.isdigit() or c == '.')
        if digits and digits != '.':
            mag = ''
            if i + 1 < len(words) and words[i + 1] in ['billion', 'million', 'trillion', 'percent', '%', 'k', 'm', 'b']:
                mag = words[i + 1]
            metrics.add(f"{digits}_{mag}")
    return metrics


def extract_semantic_features(title: str, description: str = ""):
    """Extracts normalized tokens, technical version signatures, entities, and quant metrics."""
    raw_text = f"{title or ''} {description or ''}".lower()
    for word, rep in FINANCIAL_SYNONYMS.items():
        raw_text = re.sub(rf"\b{re.escape(word)}\b", rep, raw_text)

    # Detect recognized entities
    entities = {ent for ent in KNOWN_ENTITIES if re.search(rf"\b{re.escape(ent)}\b", raw_text)}

    # Extract clean tokens
    tokens = {t for t in re.findall(r'[a-zA-Z0-9\.]+', raw_text) if len(t) >= 2 and t not in STOPWORDS}
    title_tokens = {t for t in re.findall(r'[a-zA-Z0-9]+', (title or '').lower()) if len(t) >= 2 and t not in STOPWORDS}
    versions = set(re.findall(r'\b\d+\.\d+\b', title or ''))
    metrics = extract_quant_metrics(f"{title or ''} {description or ''}")

    return tokens, title_tokens, versions, entities, metrics


def are_articles_semantic_duplicates(doc_a: dict, doc_b: dict) -> bool:
    """
    Evaluates whether two article documents report on the exact same real-world event/breakthrough.
    Operates 100% locally with zero external API calls:
    1. Entity Disambiguation: Protects separate stories on the same general topic.
    2. Metric Fingerprinting: Catches identical financial/record events described with different words.
    3. Lexical & Jaccard Overlap: Flags semantic duplicates via synonym normalization.
    """
    title_a = (doc_a.get("title") or "").strip()
    title_b = (doc_b.get("title") or "").strip()
    if not title_a or not title_b:
        return False

    tok_a, tit_a, vers_a, ent_a, met_a = extract_semantic_features(title_a, doc_a.get("description", ""))
    tok_b, tit_b, vers_b, ent_b, met_b = extract_semantic_features(title_b, doc_b.get("description", ""))

    # Guard 1: Distinct software/hardware versions represent distinct events (e.g. 3.5 vs 3.7)
    if vers_a and vers_b and not (vers_a & vers_b):
        return False

    # Guard 2: Entity Disambiguation - If both articles mention distinct primary entities, they are UNIQUE!
    # (e.g. Armenia AI vs Canada AI -> Different primary entities -> Never duplicate)
    if ent_a and ent_b and not (ent_a & ent_b):
        return False

    # Detection 1: Quantitative Metric Fingerprinting
    # If both stories share the exact same financial metric ($230B, €19B, 22%) and topic
    shared_metrics = {m for m in (met_a & met_b) if any(x in m for x in ['billion', 'million', 'trillion', '%', 'percent'])}
    if shared_metrics and (tok_a & tok_b):
        return True

    # Detection 2: Same primary entity + same numerical metric
    if (ent_a & ent_b) and (met_a & met_b):
        return True

    # Detection 3: Title Token Jaccard & Overlap
    tit_inter = tit_a & tit_b
    shorter_tit = min(len(tit_a), len(tit_b)) if (tit_a and tit_b) else 0
    if shorter_tit > 0:
        tit_overlap = len(tit_inter) / shorter_tit
        if tit_overlap >= 0.45 and len(tit_inter) >= 2:
            return True

    # Detection 4: Overall Content Token Overlap
    inter = tok_a & tok_b
    shorter = min(len(tok_a), len(tok_b)) if (tok_a and tok_b) else 0
    overlap = len(inter) / shorter if shorter > 0 else 0
    jaccard = len(inter) / len(tok_a | tok_b) if (tok_a | tok_b) else 0

    if overlap >= 0.52 or jaccard >= 0.38 or (overlap >= 0.36 and len(inter) >= 4 and (ent_a & ent_b)):
        return True

    return False


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

