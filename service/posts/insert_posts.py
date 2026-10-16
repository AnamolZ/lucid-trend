"""Pure Turso article persistence pipeline with server-side audio and static edge payload generation."""

import json
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from service.tursodb.client import TursoDBService
from service.audio.synthesizer import synthesize_audio
from service.export.static_baker import bake_static_payloads

_fallback_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="AsyncWorker")

DEFAULT_IMAGE = "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80"
AUTHOR = {"name": "NewsPluk Editorial", "role": "Systems Desk"}


def _dispatch_visual_and_audio_task(post_id: str, prompt: str, title: str, description: str = None, category: list = None, content: str = None):
    """Executes image synthesis and neural audio generation in background."""
    from service.image_helper.get_image import huggingface_image
    logging.info(f"[Worker] Background image & audio generation started for '{post_id}'...")
    try:
        # 1. Synthesize visual asset
        image_url = huggingface_image(
            prompt=prompt,
            title=title,
            description=description,
            category=category,
            max_rounds=1,
            wait_seconds=0
        )
        if image_url:
            turso = TursoDBService()
            turso.update_post_image(post_id, image_url)
            logging.info(f"[Worker] Updated image for '{post_id}' in Turso DB.")
    except Exception as img_err:
        logging.warning(f"[Worker] Background visual generation error for '{post_id}': {img_err}")

    try:
        # 2. Synthesize audio narrative
        if content:
            audio_url = synthesize_audio(post_id, title, content)
            if audio_url:
                logging.info(f"[Worker] Synthesized audio for '{post_id}': {audio_url}")
    except Exception as audio_err:
        logging.warning(f"[Worker] Background audio synthesis error for '{post_id}': {audio_err}")

    # 3. Re-bake static JSON payloads with newly synthesized image & audio
    try:
        bake_static_payloads()
    except Exception as bake_err:
        logging.warning(f"[Worker] Post-generation static bake error: {bake_err}")


def insert_posts(data_or_path, model=None, with_image: bool = True) -> list:
    """Inserts articles into Turso libSQL and triggers server-side audio & static edge baking."""
    if isinstance(data_or_path, list):
        data = data_or_path
    elif isinstance(data_or_path, str) and os.path.exists(data_or_path):
        with open(data_or_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    else:
        logging.warning("[InsertPosts] No valid data or file path provided.")
        return []

    if not data:
        logging.info("[InsertPosts] No articles to process.")
        return []

    prepared_documents = []
    for item in data:
        now_iso = datetime.now(timezone.utc).isoformat()
        post_id = item.get("id")
        doc = {
            **item,
            "image": item.get("image") or DEFAULT_IMAGE,
            "thumbnail": item.get("thumbnail") or DEFAULT_IMAGE,
            "audio_url": item.get("audio_url") or (f"/audio/{post_id}.m4a" if post_id else ""),
            "author": item.get("author") or AUTHOR,
            "source": item.get("source") or "NewsPluk Editorial",
            "published_at": item.get("published_at") or item.get("date") or now_iso,
        }
        prepared_documents.append(doc)

    # 1. Write to Turso libSQL (Single Source of Truth)
    try:
        turso_service = TursoDBService()
        inserted_ids = turso_service.insert_documents(prepared_documents, purge_older_than_days=14)
        logging.info(f"[InsertPosts] Published {len(inserted_ids)} articles to Turso Master DB.")
    except Exception as turso_err:
        logging.error(f"[InsertPosts] Turso insertion failed: {turso_err}")

    # 2. Dispatch generation (Visuals + Audio Narration)
    futures = []
    use_celery = bool(os.getenv("CELERY_BROKER_URL")) and not os.getenv("GITHUB_ACTIONS")

    for item in prepared_documents:
        post_id = item.get("id")
        image_prompt = item.get("image_prompt")
        title = item.get("title")
        description = item.get("description")
        category = item.get("category")
        content = item.get("content")

        if not post_id:
            continue

        if with_image and use_celery:
            try:
                from service.tasks.tasks import generate_and_update_image_task
                generate_and_update_image_task.delay(post_id, image_prompt, title, description, category)
                logging.info(f"[InsertPosts] Queued Celery image task for post '{post_id}'.")
            except Exception:
                futures.append(_fallback_executor.submit(
                    _dispatch_visual_and_audio_task,
                    post_id, image_prompt, title, description, category, content
                ))
        else:
            futures.append(_fallback_executor.submit(
                _dispatch_visual_and_audio_task,
                post_id, image_prompt if with_image else None, title, description, category, content
            ))

    # In GitHub Actions or single-run CLI mode, wait for asset tasks to finish before continuing
    if futures and (os.getenv("GITHUB_ACTIONS") or "--once" in sys.argv):
        logging.info(f"[InsertPosts] Awaiting completion of {len(futures)} asset generation tasks...")
        for f in futures:
            try:
                f.result(timeout=90)
            except Exception as e:
                logging.warning(f"[InsertPosts] Asset generation error: {e}")

    # 3. Immediate Initial Static Payload Bake
    try:
        bake_static_payloads()
    except Exception as bake_err:
        logging.warning(f"[InsertPosts] Initial static bake warning: {bake_err}")

    return prepared_documents
