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


def run_pipeline() -> None:
    print("=" * 60)
    print("Lucid Trend Autonomous Social & Market Intelligence Pipeline")
    print("=" * 60)

    init_db()
    profiles = load_profiles()
    if not profiles:
        print("[!] No profiles configured in data/profiles.txt.")
        return

    print(f"[+] Loaded {len(profiles)} profile(s) to monitor.")
    loader = build_instaloader()
    ocr = OCREngine()
    synthesizer = NewsSynthesizer()

    new_items = []
    for idx, user in enumerate(profiles, 1):
        print(f"[{idx}/{len(profiles)}] Checking @{user}...")
        found = scrape_profile(loader, user)
        if found:
            new_items.extend(found)
        time.sleep(random.uniform(2.0, 4.0))

    if new_items:
        print(f"\n[+] Extracting text from {len(new_items)} new post(s)/story(ies)...")
        extracted_texts = ocr.process_items(new_items)
    else:
        cached = get_recent_intel(limit=15)
        if not cached:
            print("[!] No intelligence data available.")
            return
        print("\n[+] Utilizing current intel from local database...")
        extracted_texts = [p["text"] for p in cached]

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
