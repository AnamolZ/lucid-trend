"""Slot coordinator mapping 3-hour global schedule slots to categories and managing category exclusions."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Schedule definition: 8 slots mapped across the 24h clock (anchored to US Market Open 9:30 AM EST)
# Times in Asia/Kathmandu (NPT):
# Slot 1: 17:45 NPT (08:00 EST - Pre-Open)  -> Geopolitics & Defense
# Slot 2: 20:45 NPT (11:00 EST - Post-Open) -> Finance & Global Markets
# Slot 3: 23:45 NPT (14:00 EST)             -> Technology, AI & Research
# Slot 4: 02:45 NPT (17:00 EST - US Close)  -> Finance & Global Markets
# Slot 5: 05:45 NPT (20:00 EST)             -> Technology, AI & Research
# Slot 6: 08:45 NPT (23:00 EST)             -> Geopolitics & Defense
# Slot 7: 11:45 NPT (02:00 EST)             -> Finance & Global Markets
# Slot 8: 14:45 NPT (05:00 EST)             -> Technology, AI & Research

CATEGORY_PILLARS = {
    "Technology": {
        "pillar": "Technology, AI & Scientific Research",
        "primary_category": "AI & ML",
        "allowed_domains": ["AI & ML", "Cloud & Infrastructure", "Developer Central", "Programming & Frameworks"],
        "search_queries": [
            "AI OR machine learning OR LLM OR semiconductor breakthrough when:1d",
            "cybersecurity vulnerability OR quantum computing OR developer release when:1d"
        ],
        "keywords": ["ai", "tech", "software", "chip", "quantum", "compiler", "cloud", "model"]
    },
    "Finance": {
        "pillar": "Finance & Global Markets",
        "primary_category": "Finance & Markets",
        "allowed_domains": ["Finance & Markets", "Crypto & Web3", "Macroeconomics", "Tech Strategy"],
        "search_queries": [
            "cryptocurrency OR Bitcoin OR Ethereum OR ETF market when:1d",
            "stocks OR Federal Reserve OR inflation OR oil bond market when:1d"
        ],
        "keywords": ["finance", "market", "crypto", "stock", "fed", "rate", "inflation", "oil", "bond", "treasury"]
    },
    "Geopolitics": {
        "pillar": "Geopolitics, Defense & Global Security",
        "primary_category": "Geopolitics & Defense",
        "allowed_domains": ["Geopolitics & Defense", "International Relations", "Global Security", "Tech Strategy"],
        "search_queries": [
            "geopolitics OR international sanctions OR military defense technology when:1d",
            "trade war OR NATO OR treaty foreign policy when:1d"
        ],
        "keywords": ["geopolitics", "defense", "war", "military", "sanction", "nato", "treaty", "security"]
    }
}

# The 8-slot daily sequence
SLOT_SEQUENCE = [
    {"slot": 1, "hour_est": 8,  "category_key": "Geopolitics", "label": "Pre-Market Geopolitical Intelligence"},
    {"slot": 2, "hour_est": 11, "category_key": "Finance",     "label": "Post-Open Market Volatility & Trends"},
    {"slot": 3, "hour_est": 14, "category_key": "Technology",  "label": "Midday Frontier Tech Architecture"},
    {"slot": 4, "hour_est": 17, "category_key": "Finance",     "label": "Market Close Digest & Corporate Moves"},
    {"slot": 5, "hour_est": 20, "category_key": "Technology",  "label": "Scientific & Security Breakthroughs"},
    {"slot": 6, "hour_est": 23, "category_key": "Geopolitics", "label": "Overnight Diplomatic & Strategic Shifts"},
    {"slot": 7, "hour_est": 2,  "category_key": "Finance",     "label": "Global & Asian/European Market Intelligence"},
    {"slot": 8, "hour_est": 5,  "category_key": "Technology",  "label": "Morning Engineering & Systems Releases"},
]

def resolve_active_slot(manual_category: str = None) -> Dict[str, Any]:
    """Resolves which slot and category to execute."""
    if manual_category:
        norm = manual_category.strip().lower()
        matched_key = None
        for k in CATEGORY_PILLARS:
            if k.lower() in norm or norm in k.lower():
                matched_key = k
                break
        if not matched_key:
            matched_key = "Technology"

        return {
            "slot": 0,
            "manual": True,
            "category_key": matched_key,
            "pillar_info": CATEGORY_PILLARS[matched_key],
            "label": f"Manual Override: {CATEGORY_PILLARS[matched_key]['pillar']}"
        }

    # Auto-resolve based on current EST hour
    # UTC hour:
    now_utc = datetime.now(timezone.utc)
    est_hour = (now_utc.hour - 5) % 24  # Approximate EST offset

    # Find the closest slot
    closest_slot = SLOT_SEQUENCE[0]
    min_diff = 999
    for s in SLOT_SEQUENCE:
        diff = abs(est_hour - s["hour_est"])
        if diff < min_diff:
            min_diff = diff
            closest_slot = s

    cat_key = closest_slot["category_key"]
    return {
        "slot": closest_slot["slot"],
        "manual": False,
        "category_key": cat_key,
        "pillar_info": CATEGORY_PILLARS[cat_key],
        "label": closest_slot["label"]
    }

def fetch_category_exclusions(category_key: str, limit: int = 15) -> List[str]:
    """Fetches recently published titles from Turso DB strictly matching the target category."""
    try:
        from service.tursodb.client import TursoDBService
        turso = TursoDBService()
        recent_posts = turso.fetch_recent_posts_for_export(limit=60)
        if not recent_posts:
            return []

        pillar_info = CATEGORY_PILLARS.get(category_key, {})
        allowed_domains = [d.lower() for d in pillar_info.get("allowed_domains", [])]
        keywords = pillar_info.get("keywords", [])

        category_titles = []
        for p in recent_posts:
            title = p.get("title", "").strip()
            if not title:
                continue

            cats = p.get("category", [])
            if isinstance(cats, str):
                cats = [cats]
            cats_lower = [str(c).lower() for c in cats]

            # Check if article belongs to this category
            is_match = any(any(dom in c for dom in allowed_domains) for c in cats_lower)
            if not is_match:
                # Fallback keyword match in title
                t_lower = title.lower()
                is_match = any(kw in t_lower for kw in keywords)

            if is_match and title not in category_titles:
                category_titles.append(title)
                if len(category_titles) >= limit:
                    break

        logger.info(f"[SlotCoordinator] Found {len(category_titles)} recent titles for category '{category_key}' to exclude.")
        return category_titles
    except Exception as e:
        logger.warning(f"[SlotCoordinator] Failed to fetch category exclusions: {e}")
        return []
