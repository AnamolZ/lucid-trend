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
from service.data_cleaning.gemini import are_articles_semantic_duplicates

NEWS_PLUK_ROOT = ROOT_DIR.parent / "news-pluk"

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


def extract_concise_description(summary: str, max_sentence_len: int = 125) -> str:
    """
    Extracts 2 crisp, complete, punchy sentences for cards, previews, and Shorts takeaways.
    Never truncates sentences with '...' mid-thought.
    """
    if not summary:
        return ""

    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary.strip()) if s.strip()]
    if not raw_sentences:
        return ""

    clean_sentences = []
    for s in raw_sentences:
        s = re.sub(r"^[•\s\-\*]+", "", s).strip()
        if len(s) > max_sentence_len:
            clause_match = re.search(r"^(.*?)(?:,\s*(?:while|as|amid|with|led by|including)\b)", s, re.IGNORECASE)
            if clause_match and len(clause_match.group(1)) >= 35:
                s = clause_match.group(1).strip()
            elif len(s) > max_sentence_len:
                s = s[:max_sentence_len].rsplit(" ", 1)[0].rstrip(" ,;:-")
        if not s.endswith((".", "!", "?")):
            s = f"{s}."
        clean_sentences.append(s)
        if len(clean_sentences) >= 2:
            break

    return " ".join(clean_sentences).strip()


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


def expand_story_in_depth(headline: str, key_points: List[str], summary: str = "") -> str:
    """
    Leverages Google Gemini key pool to write an in-depth, multi-paragraph authoritative analysis
    in Bloomberg / Financial Times / Stratechery monograph style.
    Guarantees deep journalism with 3 substantive paragraphs (~400-500 words per story section).
    """
    raw_body = " ".join([p.lstrip("• ").strip() for p in key_points if p.strip()])
    prompt = f"""You are a senior executive correspondent and market strategist for NewsPluk, writing in the style of Bloomberg Markets, The Financial Times, and Stratechery.

Article Headline: {headline}
Context/Key Facts: {raw_body}
Broader Executive Context: {summary}

Write an exhaustive, deeply analytical, 3-paragraph investigative narrative for this section.
Structure your narrative into exactly 3 robust paragraphs:
1. Paragraph 1 (Core Catalyst & Strategic Mechanics): Detail the immediate event, key corporate or regulatory actors, transaction structure, and operational realities.
2. Paragraph 2 (Macro & Capital Dynamics): Analyze the systemic financial ripple effects, cost of capital, supply chain bottlenecks, competitive moats, or market pricing pressures.
3. Paragraph 3 (Strategic Outlook & Structural Shifts): Detail 12-to-36 month implications for the industry, technological trajectory, regulatory headwinds, and asymmetric risks.

Rules:
- Minimum length: 350 to 500 words of substantive analytical prose.
- Zero conversational filler, zero bullet points, zero generic clichés, and zero emojis.
- Deliver strictly the 3 detailed paragraphs separated by blank lines without any headline or greeting.
"""

    # 1. Primary: Google Gemini Pool (Strictly text models, rotating across all 4 keys)
    try:
        import urllib.request
        from config.model_pool import coordinator
        keys = coordinator.raw_keys if hasattr(coordinator, "raw_keys") else []
        for k in keys:
            if not k:
                continue
            for model_name in ["models/gemini-flash-lite-latest", "models/gemini-flash-latest"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={k}"
                payload = json.dumps({
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        expanded = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        if expanded and len(expanded) > 500:
                            return expanded
                except Exception:
                    continue
    except Exception:
        pass

    # Fallback to structured analytical formatting if AI is temporarily unreachable
    fallback_paragraphs = [
        f"The recent development surrounding {headline} marks a critical juncture across enterprise and technological markets. {raw_body}",
        f"From a broader strategic standpoint, institutional capital and market infrastructure face notable shifts as enterprise operators recalibrate expectations. Amid regulatory scrutiny and infrastructure constraints, market participants are pricing in long-term macroeconomic volatility.",
        f"Looking forward, the structural impact of these operational dynamics underscores a shifting competitive landscape. As organizations adapt to tightening capital allocation and accelerated technological cycles, industry leaders must navigate both immediate execution hurdles and multi-year systemic transitions."
    ]
    return "\n\n".join(fallback_paragraphs)


def build_longform_multinews_content(headline: str, summary: str, news_items: List[Dict]) -> str:
    """
    Constructs an authoritative, comprehensive Stratechery / Stripe Press style monograph.
    Expands each news subsection with deep analytical reporting.
    """
    sections = [
        f"{summary}\n"
    ]

    for idx, item in enumerate(news_items, 1):
        h = item.get("headline", "")
        pts = item.get("key_points", []) or item.get("facts", [])
        detailed_narrative = expand_story_in_depth(h, pts, summary=summary)
        sections.append(f"## {h}\n\n{detailed_narrative}\n")

    return "\n\n".join(sections).strip()


def _load_cached_recent_articles() -> List[Dict]:
    """
    Reads recently published posts from local disk (feed.json and shorts.json)
    with ZERO database queries, causing 0 stress on Turso DB.
    """
    recent = []
    candidates = [
        NEWS_PLUK_ROOT / "public" / "api" / "feed.json",
        ROOT_DIR / "public" / "api" / "feed.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    posts = data.get("posts", [])
                    if posts:
                        recent.extend(posts[:30])
                        break
            except Exception:
                pass

    shorts_candidates = [
        NEWS_PLUK_ROOT / "public" / "api" / "shorts.json",
        ROOT_DIR / "public" / "api" / "shorts.json",
    ]
    for p in shorts_candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    shorts = data.get("shorts", [])
                    if shorts:
                        recent.extend(shorts[:30])
                        break
            except Exception:
                pass

    return recent


def dispatch_synthesized_news(payload: Dict) -> bool:
    """
    Dispatches news with in-memory zero-DB deduplication:
    1. Compares each candidate news item against cached recent articles.
    2. Filters out duplicates; keeps ONLY genuinely unique items.
    3. If zero items are unique, skips DB writes cleanly (0 DB stress).
    4. Only writes and bakes if at least 1 unique item exists.
    """
    headline = payload.get("headline", "")
    executive_summary = payload.get("executive_summary", "")
    facts = payload.get("facts", [])
    news_items = payload.get("news_items", [])

    if not headline or not news_items:
        print("[Dispatcher] Missing headline or news items.")
        return False

    # 1. Zero-DB Read: Load existing recent articles from local JSON cache
    cached_recent = _load_cached_recent_articles()

    # 2. Filter news items: Keep ONLY unique items, drop duplicates
    unique_news_items = []
    for item in news_items:
        item_title = item.get("headline", "").strip()
        item_desc = " ".join(item.get("facts", []) or item.get("key_points", []))
        candidate_doc = {"title": item_title, "description": item_desc}

        is_dup = False
        for seen in cached_recent:
            seen_doc = {"title": seen.get("title", ""), "description": seen.get("description", "")}
            if are_articles_semantic_duplicates(candidate_doc, seen_doc):
                is_dup = True
                print(f"[Deduplication] Dropping duplicate item: '{item_title}' (matches '{seen.get('title')}')")
                break

        if not is_dup:
            unique_news_items.append(item)

    print(f"[Deduplication] Evaluated {len(news_items)} item(s) -> {len(unique_news_items)} unique item(s) remaining.")

    # 3. If NO unique items exist, abort early without touching the database!
    if not unique_news_items:
        print("[Dispatcher] Zero unique items in this cycle. Skipping database write and CDN deploy cleanly.")
        return False

    turso = TursoDBService()
    now_iso = datetime.now(timezone.utc).isoformat()
    lead_temp_image = TEMP_DIR / "lead_editorial.jpg"

    # Determine author rotation from local cache
    author_idx = 0
    if cached_recent:
        last_auth = cached_recent[0].get("author", {})
        last_name = last_auth.get("name") if isinstance(last_auth, dict) else str(last_auth)
        if "Anamol" in last_name:
            author_idx = 1
    assigned_author = AUTHORS[author_idx]

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    clean_slug = slugify(headline)
    post_id = f"macro-dispatch-{date_str}-{clean_slug[:45]}"
    target_img_name = f"{post_id}.jpg"
    image_web_path = f"/images/{target_img_name}"

    dest_roots = [ROOT_DIR]
    if NEWS_PLUK_ROOT.exists():
        dest_roots.append(NEWS_PLUK_ROOT)

    # Ensure lead image exists, or acquire it directly if missing
    if not lead_temp_image.exists():
        try:
            from service.intel_extractor.image_search import acquire_editorial_thumbnail
            acquire_editorial_thumbnail(headline, summary=executive_summary, post_id="lead_editorial")
        except Exception as e:
            print(f"[Dispatcher] Warning: Failed on-demand thumbnail acquisition: {e}")

    # Copy lead image to public CDN images
    if lead_temp_image.exists():
        for dest_root in dest_roots:
            img_dest = dest_root / "public" / "images"
            img_dest.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(lead_temp_image, img_dest / target_img_name)
                # Also generate webp companion
                try:
                    from PIL import Image
                    webp_path = img_dest / f"{post_id}.webp"
                    with Image.open(lead_temp_image) as im:
                        im.save(webp_path, "WEBP", quality=85)
                except Exception:
                    pass
            except Exception:
                pass

    concise_desc = extract_concise_description(executive_summary)
    full_content = build_longform_multinews_content(headline, executive_summary, unique_news_items)
    image_prompt = build_breaking_news_image_prompt(headline)
    categories = map_to_approved_categories(unique_news_items)

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

    # Only write full post to DB if post headline is unique
    post_is_dup = any(
        are_articles_semantic_duplicates({"title": headline, "description": concise_desc}, {"title": s.get("title", ""), "description": s.get("description", "")})
        for s in cached_recent
    )

    receipt_file = TEMP_DIR / "new_post_receipt.json"
    if receipt_file.exists():
        try:
            receipt_file.unlink()
        except Exception:
            pass

    if not post_is_dup:
        print(f"\n[Dispatcher] Storing unified multi-news article in 'posts' table (ID: {post_id})...")
        turso.insert_documents([post_doc])
        # Record one-time notification receipt strictly for genuinely new articles
        try:
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            with open(receipt_file, "w", encoding="utf-8") as rf:
                json.dump({"post_id": post_id, "title": headline, "description": concise_desc}, rf)
        except Exception as r_err:
            print(f"[Dispatcher] Receipt write warning: {r_err}")

        print(f"[Dispatcher] Generating neural audio narration for '{post_id}'...")
        try:
            audio_res = synthesize_audio(post_id, headline, full_content)
            if audio_res:
                print(f"[Dispatcher] Audio briefing generated successfully: {audio_res}")
        except Exception as e:
            print(f"[Dispatcher] Audio generation notice: {e}")
    else:
        print(f"[Dispatcher] Main headline already published previously. Skipping post insert and push receipt.")

    # --- DEDICATED SHORT-FORM CARDS FOR UNIQUE ITEMS ONLY ---
    shorts_docs = []
    for idx, item in enumerate(unique_news_items, 1):
        item_headline = item.get("headline", "").strip()
        if not item_headline:
            continue
        item_slug = slugify(item_headline)
        item_short_id = f"short-{date_str}-{item_slug[:40]}-{idx}"
        item_img_name = f"{item_short_id}.jpg"
        item_img_path = f"/images/{item_img_name}"

        if lead_temp_image.exists():
            for dest_root in dest_roots:
                img_dest = dest_root / "public" / "images"
                img_dest.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(lead_temp_image, img_dest / item_img_name)
                except Exception:
                    pass

        item_facts = item.get("facts") or []
        if not item_facts:
            kw = set(item_headline.lower().split())
            matched = [f for f in facts if any(w in f.lower() for w in kw if len(w) > 4)]
            item_facts = matched if matched else (item.get("key_points") or facts[:3])

        clean_item_facts = [f for f in item_facts if f and f.strip()][:3]
        item_cat = [item.get("category", "Shorts"), "Shorts"]

        shorts_docs.append({
            "id": item_short_id,
            "title": item_headline,
            "facts": clean_item_facts,
            "news_items": [item],
            "image": item_img_path,
            "category": item_cat,
            "published_at": now_iso,
        })

    if shorts_docs:
        print(f"[Dispatcher] Storing {len(shorts_docs)} unique dedicated short card(s) in 'shorts' table...")
        insert_shorts(shorts_docs)

    print("[Dispatcher] Baking static edge payloads (feed.json, shorts.json, posts/*.json)...")
    bake_res = bake_static_payloads()
    print(f"[Dispatcher] Edge cache baked successfully: {bake_res}")

    return True
