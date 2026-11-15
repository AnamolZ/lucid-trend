import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from config.settings import ROOT_DIR, TEMP_DIR
from service.tursodb.client import TursoDBService
from service.shorts.insert_shorts import insert_shorts
from service.export.static_baker import bake_static_payloads
from service.audio.synthesizer import synthesize_audio

NEWS_PLUK_MAIN_ROOT = ROOT_DIR.parent / "news-pluk-main"
NEWS_PLUK_REPO_ROOT = ROOT_DIR.parent / "news-pluk-repo"

# Strict official categories in Lucid Trend
APPROVED_CATEGORIES = [
    "Breaking News",
    "Finance & Markets",
    "AI & ML",
    "Cloud & Infrastructure",
    "Advancement",
    "Geopolitics & Defense",
]

AUTHORS = [
    {
        "name": "Anamol Dhakal",
        "role": "Backend System Developer",
        "avatar": "https://newspluk.com/avatar-anamol.webp",
    },
    {
        "name": "Bina Pokhrel",
        "role": "Researcher",
        "avatar": "https://newspluk.com/avatar-bina.webp",
    },
]


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", cleaned).strip("-")[:75]


def extract_concise_description(summary: str, max_length: int = 200) -> str:
    """Extract a clean, punchy 1-2 sentence synopsis for cards and previews."""
    if not summary:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", summary.strip())
    desc = sentences[0] if sentences else summary
    if len(desc) < 80 and len(sentences) > 1:
        desc = f"{sentences[0]} {sentences[1]}"
    if len(desc) > max_length:
        desc = desc[:max_length].rsplit(" ", 1)[0] + "..."
    return desc.strip()


def build_breaking_news_image_prompt(headline: str) -> str:
    """Build a professional, cinematic broadcast newsroom image prompt."""
    return (
        f"A dramatic, wide-angle cinematic shot of a premier international financial news desk and broadcast floor. "
        f"Wall-mounted monitors display live stock ticker ribbons, red and green market depth charts, and breaking macroeconomic chyrons. "
        f"Senior financial correspondents in tailored business attire analyze live data under cool professional broadcast studio lighting. "
        f"Subject: {headline}. Photorealistic 16:9 composition, authentic Reuters newsroom realism, shallow depth of field."
    )


def map_to_approved_categories(news_items: List[Dict]) -> List[str]:
    """Map extracted topics strictly to the 6 official system categories."""
    cats = ["Breaking News", "Finance & Markets"]
    corpus = " ".join([item.get("headline", "") + " " + item.get("category", "") for item in news_items]).lower()

    if any(k in corpus for k in ["ai", "gpu", "chip", "nvidia", "silicon", "neural", "llm"]):
        if "AI & ML" not in cats:
            cats.append("AI & ML")
    if any(k in corpus for k in ["datacenter", "cloud", "server", "telecom", "infrastructure", "faa"]):
        if "Cloud & Infrastructure" not in cats:
            cats.append("Cloud & Infrastructure")
    if any(k in corpus for k in ["diplomacy", "sanctions", "uk government", "policy", "defense"]):
        if "Geopolitics & Defense" not in cats:
            cats.append("Geopolitics & Defense")

    return [c for c in cats if c in APPROVED_CATEGORIES][:3]


def build_longform_multinews_content(headline: str, summary: str, news_items: List[Dict]) -> str:
    """
    Constructs an authoritative Stratechery / Stripe Press style monograph.
    No source at the bottom (Source is stored cleanly in the database column).
    """
    # Opening thesis & stakes
    sections = [
        f"{summary}\n"
    ]

    # Bespoke chapter subheadings with narrative prose analysis
    for idx, item in enumerate(news_items, 1):
        h = item.get("headline", "")
        pts = item.get("key_points", [])
        
        # Turn raw bullets into clean editorial narrative paragraphs
        clean_pts = [p.lstrip("• ").strip() for p in pts if p.strip()]
        narrative_body = " ".join(clean_pts)

        sections.append(f"## {h}\n{narrative_body}\n")

    return "\n\n".join(sections).strip()


def dispatch_synthesized_news(payload: Dict) -> bool:
    """
    1. Publishes 1 comprehensive multi-news dispatch into 'posts' (all 14 columns 100% filled).
    2. Publishes dedicated vertical cards into 'shorts' (facts + story snippets).
    3. Copies lead image to CDN assets.
    4. Triggers static edge baking for feed.json, shorts.json, and posts/{id}.json.
    """
    headline = payload.get("headline", "")
    executive_summary = payload.get("executive_summary", "")
    facts = payload.get("facts", [])
    news_items = payload.get("news_items", [])

    if not headline or not news_items:
        print("[Dispatcher] Missing headline or news items.")
        return False

    turso = TursoDBService()
    now_iso = datetime.now(timezone.utc).isoformat()
    lead_temp_image = TEMP_DIR / "lead_editorial.jpg"

    # Determine author rotation
    author_idx = 0
    recent = turso.fetch_recent_posts_for_export(limit=5)
    if recent:
        last_auth = recent[0].get("author", {})
        last_name = last_auth.get("name") if isinstance(last_auth, dict) else str(last_auth)
        if "Anamol" in last_name:
            author_idx = 1
    assigned_author = AUTHORS[author_idx]

    # --- 1. COMPREHENSIVE MULTI-NEWS POST (Table: posts) ---
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    clean_slug = slugify(headline)
    post_id = f"macro-dispatch-{date_str}-{clean_slug[:45]}"
    target_img_name = f"{post_id}.jpg"
    image_web_path = f"/images/{target_img_name}"

    # Copy lead image to public CDN images
    if lead_temp_image.exists():
        dest_roots = [ROOT_DIR, NEWS_PLUK_MAIN_ROOT]
        if NEWS_PLUK_REPO_ROOT.exists():
            dest_roots.append(NEWS_PLUK_REPO_ROOT)
        for dest_root in dest_roots:
            img_dest = dest_root / "public" / "images"
            img_dest.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(lead_temp_image, img_dest / target_img_name)
            except Exception:
                pass

    concise_desc = extract_concise_description(executive_summary)
    full_content = build_longform_multinews_content(headline, executive_summary, news_items)
    image_prompt = build_breaking_news_image_prompt(headline)
    categories = map_to_approved_categories(news_items)

    post_doc = {
        "id": post_id,
        "title": headline,
        "slug": clean_slug,
        "description": concise_desc,
        "content": full_content,
        "image": image_web_path,
        "thumbnail": image_web_path,
        "image_prompt": image_prompt,
        "category": categories,
        "author": assigned_author,
        "source": "Lucid",
        "published_at": now_iso,
        "audio_url": f"/audio/{post_id}.m4a",
    }

    print(f"\n[Dispatcher] Storing unified multi-news article in 'posts' table (ID: {post_id})...")
    turso.insert_documents([post_doc])

    # Synthesize neural voice briefing for the dispatch (Edge TTS)
    print(f"[Dispatcher] Generating neural audio narration for '{post_id}'...")
    try:
        audio_res = synthesize_audio(post_id, headline, full_content)
        if audio_res:
            print(f"[Dispatcher] Audio briefing generated successfully: {audio_res}")
    except Exception as e:
        print(f"[Dispatcher] Audio generation notice: {e}")

    # --- 2. DEDICATED SHORT-FORM CARD (Table: shorts) ---
    short_id = f"short-{date_str}-{clean_slug[:45]}"
    short_img_name = f"{short_id}.jpg"
    short_img_path = f"/images/{short_img_name}"

    if lead_temp_image.exists():
        dest_roots = [ROOT_DIR, NEWS_PLUK_MAIN_ROOT]
        if NEWS_PLUK_REPO_ROOT.exists():
            dest_roots.append(NEWS_PLUK_REPO_ROOT)
        for dest_root in dest_roots:
            img_dest = dest_root / "public" / "images"
            img_dest.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(lead_temp_image, img_dest / short_img_name)
            except Exception:
                pass

    shorts_doc = {
        "id": short_id,
        "title": headline,
        "facts": facts,
        "news_items": news_items,
        "image": short_img_path,
        "category": ["Breaking News", "Shorts"],
        "published_at": now_iso,
    }

    print(f"[Dispatcher] Storing dedicated short card in 'shorts' table (ID: {short_id})...")
    insert_shorts([shorts_doc])

    print("[Dispatcher] Baking static edge payloads (feed.json, shorts.json, posts/*.json)...")
    bake_res = bake_static_payloads()
    print(f"[Dispatcher] Edge cache baked successfully: {bake_res}")

    return True
