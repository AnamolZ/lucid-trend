"""Article persistence pipeline with immediate publication and decoupled image queuing."""

import json
import os
import logging
import threading
from service.tasks.tasks import generate_and_update_image_task, AUTHOR, DEFAULT_IMAGE
from service.mongodb.client import MongoDBService

def _dispatch_image_task_fallback(post_id: str, prompt: str, title: str):
    """Executes image generation in a background thread when Celery broker is unavailable."""
    from service.image_helper.get_image import huggingface_image
    logging.info(f"[ImageFallbackThread] Background image generation started for '{post_id}'...")
    try:
        image_url = huggingface_image(prompt=prompt, max_rounds=3, wait_seconds=300)
        if image_url:
            mongo = MongoDBService()
            mongo.update_post_image(post_id, image_url)
            logging.info(f"[ImageFallbackThread] Successfully updated post '{post_id}' in MongoDB.")
    except Exception as e:
        logging.warning(f"[ImageFallbackThread] Background generation error for '{post_id}': {e}")

def insert_posts(data_or_path, model=None) -> list:
    """Inserts articles into MongoDB immediately with default images, delegating visual generation to background tasks."""
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

    # Assign default visual placeholders and author metadata for instant publication
    prepared_documents = []
    for item in data:
        doc = {
            **item,
            "image": item.get("image") or DEFAULT_IMAGE,
            "thumbnail": item.get("thumbnail") or DEFAULT_IMAGE,
            "author": item.get("author") or AUTHOR,
        }
        prepared_documents.append(doc)

    mongo_service = MongoDBService()
    inserted_ids = mongo_service.insert_documents(prepared_documents)
    logging.info(f"[InsertPosts] Published {len(prepared_documents)} articles to MongoDB with placeholder images.")

    # Dispatch asynchronous image synthesis tasks without blocking the caller
    for item in prepared_documents:
        post_id = item.get("id")
        image_prompt = item.get("image_prompt")
        title = item.get("title")

        if not post_id:
            continue

        try:
            generate_and_update_image_task.delay(post_id, image_prompt, title)
            logging.info(f"[InsertPosts] Queued background image task for post '{post_id}' via Celery.")
        except Exception as celery_err:
            logging.warning(
                f"[InsertPosts] Celery broker offline ({celery_err}). Spawning background thread fallback..."
            )
            thread = threading.Thread(
                target=_dispatch_image_task_fallback,
                args=(post_id, image_prompt, title),
                daemon=True
            )
            thread.start()

    return prepared_documents