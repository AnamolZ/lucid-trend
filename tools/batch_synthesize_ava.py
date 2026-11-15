import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

sys.path.insert(0, r"D:\lucid-trend-system\lucid-trend")
from dotenv import load_dotenv
load_dotenv(r"D:\lucid-trend-system\lucid-trend\.env")

from service.tursodb.client import TursoDBService
from service.audio.synthesizer import synthesize_audio_async
from service.export.static_baker import bake_static_payloads

TARGET_OUTPUT_DIRS = [
    r"D:\lucid-trend-system\news-pluk\public\audio",
    r"D:\lucid-trend-system\lucid-trend\public\audio",
]

for d in TARGET_OUTPUT_DIRS:
    os.makedirs(d, exist_ok=True)

async def process_post(sem, post, idx, total):
    async with sem:
        post_id = post["id"]
        title = post.get("title", "")
        content = post.get("content", "") or post.get("description", "")
        logging.info(f"[{idx}/{total}] Synthesizing Ava narration for '{post_id}'...")

        try:
            url = await synthesize_audio_async(
                post_id=post_id,
                title=title,
                content=content,
                output_dirs=TARGET_OUTPUT_DIRS,
                voice="en-US-AvaNeural"
            )
            logging.info(f"[{idx}/{total}] Done '{post_id}': {url}")
            return post_id, True
        except Exception as e:
            logging.error(f"[{idx}/{total}] Error for '{post_id}': {e}")
            return post_id, False

async def main():
    turso = TursoDBService()
    posts = turso.fetch_recent_posts_for_export(limit=100)
    total = len(posts)
    logging.info(f"Found {total} posts to synthesize with Ava (en-US-AvaNeural)")

    # Concurrency limit of 3 to avoid rate limits
    sem = asyncio.Semaphore(3)
    tasks = [process_post(sem, p, i + 1, total) for i, p in enumerate(posts)]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for _, ok in results if ok)
    logging.info(f"Completed audio synthesis: {success_count}/{total} successful with Ava.")

    # Re-bake all static payloads
    logging.info("Baking updated static JSON payloads...")
    bake_static_payloads()
    logging.info("All server assets and static dispatches successfully updated with Ava audio!")

if __name__ == "__main__":
    asyncio.run(main())

