"""
Zero-DB Git-Backed Cache for Scraped Intelligence.
Maintains a rolling FIFO queue of the last 5 seen post IDs in news-pluk/public/api/seen_intel.json.
- When a new post comes in, it is prepended to the top.
- The bottom post is automatically evicted once the list reaches 5.
- Zero network latency, zero database costs, 100% persistent across GitHub Actions runs.
"""

import json
from pathlib import Path
from typing import List, Dict

SEEN_CACHE_PATHS = [
    Path("news-pluk/public/api/seen_intel.json"),
    Path("../news-pluk/public/api/seen_intel.json"),
    Path("public/api/seen_intel.json"),
    Path("data/seen_intel.json"),
]

MAX_CAPACITY = 5


def _get_cache_file() -> Path:
    for p in SEEN_CACHE_PATHS:
        if p.exists():
            return p
    default_p = SEEN_CACHE_PATHS[0]
    default_p.parent.mkdir(parents=True, exist_ok=True)
    return default_p


def _load_seen_ids() -> List[str]:
    cache_file = _get_cache_file()
    if not cache_file.exists():
        return []
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass
    return []


def _save_seen_ids(ids: List[str]) -> None:
    cache_file = _get_cache_file()
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        # Keep strictly the newest MAX_CAPACITY (last 5)
        trimmed = ids[:MAX_CAPACITY]
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, indent=2)
    except Exception as e:
        print(f"[SeenCache] Warning saving cache file: {e}")


def init_db() -> None:
    """Initializes the seen cache file if not present."""
    cache_file = _get_cache_file()
    if not cache_file.exists():
        _save_seen_ids([])


def is_post_seen(post_id: str) -> bool:
    """Checks whether the given post_id is already in the top 5 seen cache."""
    if not post_id:
        return False
    seen = _load_seen_ids()
    return str(post_id).strip() in seen


def save_post(post_id: str, profile: str = "", published_at: str = "", text: str = "") -> bool:
    """
    Prepends the new post_id to the top of the FIFO cache.
    Evicts the oldest bottom post if length exceeds 5.
    """
    clean_id = str(post_id).strip()
    if not clean_id:
        return False

    current = _load_seen_ids()
    if clean_id in current:
        return False

    # Insert at top, evict oldest from bottom
    updated = [clean_id] + current
    _save_seen_ids(updated)
    return True


def get_recent_intel(limit: int = 5) -> List[Dict]:
    """Fallback stub for pipeline interface."""
    return []
