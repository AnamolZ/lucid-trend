from datetime import datetime, timezone
"""Article persistence pipeline with dual-write to Turso (serving) and MongoDB (compressed backup)."""

import json
import os
import io
import base64
import logging
import threading
from PIL import Image

from service.tasks.tasks import generate_and_update_image_task, AUTHOR, DEFAULT_IMAGE
from service.mongodb.client import MongoDBService
from service.tursodb.client import TursoDBService

def compress_image_base64_for_mongo(data_uri: str, max_bytes: int = 400 * 1024) -> str:
    """Compresses base64 images under max_bytes for MongoDB storage only."""
    if not data_uri or not data_uri.startswith("data:image"):
        return data_uri

    try:
        header, b64data = data_uri.split(",", 1)
        raw_bytes = base64.b64decode(b64data)
        if len(raw_bytes) <= max_bytes:
            return data_uri

        img = Image.open(io.BytesIO(raw_bytes))
        img = img.convert("RGB")
        max_dim = 1200
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        quality = 80
        out_buf = io.BytesIO()
        img.save(out_buf, format="WEBP", quality=quality, optimize=True)

        while out_buf.tell() > max_bytes and quality > 40:
            quality -= 10
            out_buf = io.BytesIO()
            img.save(out_buf, format="WEBP", quality=quality, optimize=True)

        compressed_b64 = base64.b64encode(out_buf.getvalue()).decode("utf-8")
        logging.info(f"[MongoCompressor] Compressed Mongo image from {len(raw_bytes)//1024}KB to {out_buf.tell()//1024}KB.")
        return f"data:image/webp;base64,{compressed_b64}"
    except Exception as e:
        logging.warning(f"[MongoCompressor] Error compressing image for Mongo: {e}")
        return data_uri

def _dispatch_image_task_fallback(post_id: str, prompt: str, title: str, description: str = None, category: list = None):
    """Executes image generation in background thread when Celery is offline."""
    from service.image_helper.get_image import huggingface_image
    logging.info(f"[ImageFallbackThread] Background image generation started for '{post_id}'...")
    try:
        image_url = huggingface_image(
            prompt=prompt,
            title=title,
            description=description,
            category=category,
            max_rounds=1,
            wait_seconds=0
        )
        if image_url:
            # 1. Update Turso (Primary Serving DB - Full Quality Uncompressed)
            try:
                turso = TursoDBService()
                turso.update_post_image(post_id, image_url)
                logging.info(f"[ImageFallbackThread] Updated post '{post_id}' in Turso DB.")
            except Exception as turso_err:
                logging.error(f"[ImageFallbackThread] Turso update error for '{post_id}': {turso_err}")

            # 2. Update MongoDB (Backup DB - Compressed < 500KB)
            try:
                mongo_img = compress_image_base64_for_mongo(image_url, 400 * 1024)
                mongo = MongoDBService()
                mongo.update_post_image(post_id, mongo_img)
                logging.info(f"[ImageFallbackThread] Updated post '{post_id}' in MongoDB.")
            except Exception as mongo_err:
                logging.error(f"[ImageFallbackThread] MongoDB update error for '{post_id}': {mongo_err}")
    except Exception as e:
        logging.warning(f"[ImageFallbackThread] Background generation error for '{post_id}': {e}")

def insert_posts(data_or_path, model=None, with_image: bool = True) -> list:
    """Inserts articles into Turso (serving) and MongoDB (compressed backup)."""
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
        doc = {
            **item,
            "image": item.get("image") or DEFAULT_IMAGE,
            "thumbnail": item.get("thumbnail") or DEFAULT_IMAGE,
            "author": item.get("author") or AUTHOR,
            "source": item.get("source") or "NewsPluk Editorial",
            "published_at": item.get("published_at") or item.get("date") or now_iso,
        }
        prepared_documents.append(doc)

    # 1. Write to Turso DB (Serving - Full Original Quality)
    try:
        turso_service = TursoDBService()
        turso_ids = turso_service.insert_documents(prepared_documents, purge_older_than_days=14)
        logging.info(f"[InsertPosts] Published {len(turso_ids)} articles to Turso DB.")
    except Exception as turso_err:
        logging.error(f"[InsertPosts] Turso insertion failed: {turso_err}")

    # 2. Write to MongoDB (Backup - Compressed Images < 500KB)
    try:
        mongo_docs = []
        for d in prepared_documents:
            m_doc = dict(d)
            m_doc["image"] = compress_image_base64_for_mongo(d.get("image"), 400 * 1024)
            m_doc["thumbnail"] = compress_image_base64_for_mongo(d.get("thumbnail"), 200 * 1024)
            mongo_docs.append(m_doc)

        mongo_service = MongoDBService()
        inserted_ids = mongo_service.insert_documents(mongo_docs, purge_older_than_days=14)
        logging.info(f"[InsertPosts] Published {len(inserted_ids)} articles to MongoDB backup.")
    except Exception as mongo_err:
        logging.error(f"[InsertPosts] MongoDB backup insertion failed: {mongo_err}")

    # Dispatch visual generation tasks
    if with_image:
        for item in prepared_documents:
            post_id = item.get("id")
            image_prompt = item.get("image_prompt")
            title = item.get("title")
            if not post_id:
                continue

            description = item.get("description")
            category = item.get("category")

            try:
                generate_and_update_image_task.delay(post_id, image_prompt, title, description, category)
                logging.info(f"[InsertPosts] Queued background image task for post '{post_id}' via Celery.")
            except Exception as celery_err:
                logging.warning(
                    f"[InsertPosts] Celery broker offline ({celery_err}). Spawning background thread fallback..."
                )
                thread = threading.Thread(
                    target=_dispatch_image_task_fallback,
                    args=(post_id, image_prompt, title, description, category),
                    daemon=True
                )
                thread.start()
    else:
        logging.info("[InsertPosts] Image synthesis skipped (--without image active).")

    return prepared_documents
