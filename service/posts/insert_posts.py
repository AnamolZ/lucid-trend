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

import hashlib
import threading

TOPIC_FALLBACK_POOLS = {
    "quantum": [
        "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1507668077129-56e32842fceb?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=1200&q=80",
    ],
    "robotics": [
        "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1561557944-6e7860d1a7eb?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1531746790731-6c087fecd65a?auto=format&fit=crop&w=1200&q=80",
    ],
    "chips": [
        "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=1200&q=80",
    ],
    "cloud": [
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
    ],
    "software": [
        "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?auto=format&fit=crop&w=1200&q=80",
    ],
    "security": [
        "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1510511459019-5dda7724fd87?auto=format&fit=crop&w=1200&q=80",
    ],
    "general": [
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?auto=format&fit=crop&w=1200&q=80",
    ]
}

AUTHOR = {"name": "NewsPluk Editorial", "role": "Systems Desk"}
_image_synthesis_lock = threading.Lock()


def get_topic_fallback_image(title: str = "", description: str = "", category: list = None, post_id: str = "") -> str:
    """Deterministically returns a unique, topic-relevant high-resolution image for every article."""
    corpus = f"{title or ''} {description or ''} {' '.join(category) if isinstance(category, list) else ''}".lower()

    if any(k in corpus for k in ["quantum", "qubit", "cryostat", "superconductor"]):
        pool = TOPIC_FALLBACK_POOLS["quantum"]
    elif any(k in corpus for k in ["robot", "humanoid", "actuator", "drone", "embodied"]):
        pool = TOPIC_FALLBACK_POOLS["robotics"]
    elif any(k in corpus for k in ["chip", "semiconductor", "dram", "wafer", "nanostack", "gpu", "tpu", "hardware", "silicon"]):
        pool = TOPIC_FALLBACK_POOLS["chips"]
    elif any(k in corpus for k in ["cloud", "datacenter", "server", "cluster", "kubernetes"]):
        pool = TOPIC_FALLBACK_POOLS["cloud"]
    elif any(k in corpus for k in ["security", "vulnerability", "hack", "cyber", "malware", "firewall"]):
        pool = TOPIC_FALLBACK_POOLS["security"]
    elif any(k in corpus for k in ["code", "developer", "ide", "compiler", "rust", "python", "software", "api"]):
        pool = TOPIC_FALLBACK_POOLS["software"]
    else:
        pool = TOPIC_FALLBACK_POOLS["general"]

    # Use hash of post_id / title so every unique post deterministically gets its own distinct photo
    key = post_id or title or "newspluk-default"
    idx = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % len(pool)
    return pool[idx]


def _dispatch_visual_and_audio_task(post_id: str, prompt: str, title: str, description: str = None, category: list = None, content: str = None):
    """Executes image synthesis and neural audio generation in background with serialized rate-limit pacing."""
    from service.image_helper.get_image import huggingface_image
    logging.info(f"[Worker] Background image & audio generation started for '{post_id}'...")
    try:
        # 1. Synthesize visual asset under lock to prevent concurrent rate-limit collisions
        with _image_synthesis_lock:
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
        fallback_img = get_topic_fallback_image(
            title=item.get("title", ""),
            description=item.get("description", ""),
            category=item.get("category"),
            post_id=post_id or ""
        )
        doc = {
            **item,
            "image": item.get("image") or fallback_img,
            "thumbnail": item.get("thumbnail") or fallback_img,
            "audio_url": item.get("audio_url") or (f"/audio/{post_id}.m4a" if post_id else ""),
            "author": item.get("author") or AUTHOR,
            "source": item.get("source") or "NewsPluk Editorial",
            "published_at": item.get("published_at") or item.get("date") or now_iso,
        }
        prepared_documents.append(doc)

    # 1. Pre-Insertion Semantic Deduplication against existing database posts
    try:
        from service.data_cleaning.gemini import are_articles_semantic_duplicates
        turso_service = TursoDBService()
        existing_recent = turso_service.fetch_recent_posts_for_export(limit=50)

        unique_docs = []
        for doc in prepared_documents:
            is_dup = False
            for exist in existing_recent:
                if doc.get("id") == exist.get("id") or are_articles_semantic_duplicates(doc, exist):
                    logging.info(f"[InsertPosts] Skipping semantic duplicate of '{exist.get('title')}': '{doc.get('title')}'")
                    is_dup = True
                    break

            if not is_dup:
                for accepted in unique_docs:
                    if are_articles_semantic_duplicates(doc, accepted):
                        logging.info(f"[InsertPosts] Skipping batch duplicate of '{accepted.get('title')}': '{doc.get('title')}'")
                        is_dup = True
                        break

            if not is_dup:
                unique_docs.append(doc)

        prepared_documents = unique_docs
    except Exception as dedup_err:
        logging.warning(f"[InsertPosts] Pre-deduplication check warning: {dedup_err}")

    if not prepared_documents:
        logging.info("[InsertPosts] All incoming articles were semantic duplicates of existing dispatches. Skipping insertion.")
        return []

    # 2. Write to Turso libSQL (Single Source of Truth)
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
