import json
import random
import time
from datetime import datetime, timezone

from config.settings import OUTPUT_JSON_FILE
from service.intel_extractor.utils import load_profiles
from service.intel_extractor.db import init_db, get_recent_intel
from service.intel_extractor.scraper import build_instaloader, scrape_profile
from service.intel_extractor.ocr import OCREngine
from service.intel_extractor.synthesizer import NewsSynthesizer
from service.intel_extractor.image_search import acquire_editorial_thumbnail
from service.intel_extractor.dispatcher import dispatch_synthesized_news
from engine.live_scout import scout_category_intel


def run_pipeline() -> None:
    print("=" * 60)
    print("Lucid Trend Autonomous Social & Market Intelligence Pipeline")
    print("=" * 60)

    init_db()
    profiles = load_profiles()
    loader = build_instaloader()
    ocr = OCREngine()
    synthesizer = NewsSynthesizer()

    new_items = []
    if profiles:
        print(f"[+] Checking {len(profiles)} profile(s) for public updates...")
        for idx, user in enumerate(profiles, 1):
            print(f"[{idx}/{len(profiles)}] Checking @{user}...")
            found = scrape_profile(loader, user)
            if found:
                new_items.extend(found)
            time.sleep(random.uniform(1.0, 2.5))

    extracted_texts = []
    if new_items:
        print(f"\n[+] Extracting text from {len(new_items)} new post(s)...")
        extracted_texts = ocr.process_items(new_items)

    # Resilient Autonomous Fallback: If Instagram blocks cloud IP, scout verified breaking market news
    if not extracted_texts:
        print("\n[!] Social media feed returned no fresh items. Engaging real-time verified intelligence scout...")
        queries = [
            "crypto market bitcoin ethereum",
            "wall street stock market nvidia tech",
            "federal reserve interest rates inflation",
            "ai artificial intelligence developments",
        ]
        scouted = scout_category_intel("Finance", queries, max_items=12)
        if scouted:
            print(f"[+] Scouted {len(scouted)} verified breaking developments.")
            for s in scouted:
                extracted_texts.append(f"Headline: {s['title']}\nSnippet: {s.get('snippet', '')}\nSource: {s.get('source', '')}")
        else:
            cached = get_recent_intel(limit=15)
            if cached:
                print("\n[+] Utilizing recent intelligence from local database...")
                extracted_texts = [p["text"] for p in cached]

    if not extracted_texts:
        print("[!] No intelligence data available to synthesize.")
        return

    combined_text = "\n---\n".join(extracted_texts)
    print(f"[+] Processing {len(combined_text)} characters with AI synthesizer...")

    data = synthesizer.synthesize(combined_text)
    if not data:
        print("[!] Synthesis failed.")
        return

    final_payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "headline": data.get("headline", ""),
        "executive_summary": data.get("executive_summary", ""),
        "facts": data.get("facts") or data.get("quick_facts") or [],
        "news_items": data.get("news_items", []),
    }

    # Acquire lead editorial image to temp/
    lead_headline = final_payload["headline"] or "Market Intelligence Digest"
    lead_summary = final_payload["executive_summary"] or ""
    acquire_editorial_thumbnail(lead_headline, summary=lead_summary, post_id="lead_editorial")

    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"SUCCESS! Clean news output generated: {OUTPUT_JSON_FILE}")
    print("=" * 60)
    print(json.dumps(final_payload, indent=2, ensure_ascii=False))

    # Dual Dispatch to 'posts' and dedicated 'shorts' table + Static Baking
    dispatch_synthesized_news(final_payload)


if __name__ == "__main__":
    run_pipeline()
