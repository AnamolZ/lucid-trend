import json
import os
import logging
from celery import group
from service.tasks.tasks import generate_image_task
from service.mongodb.client import MongoDBService

def insert_posts(data_or_path, model=None):
    """
    Processes articles, generates images via Celery, and inserts into MongoDB.
    Accepts either a list of article dicts or a JSON file path.
    """
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

    logging.info(f"[InsertPosts] Dispatching {len(data)} articles to Celery image worker...")
    job = group([generate_image_task.s(item) for item in data])
    result = job.apply_async()
    documents = result.join()

    if not documents:
        logging.warning("[InsertPosts] Celery worker returned no documents.")
        return []

    mongo_service = MongoDBService()
    inserted_ids = mongo_service.insert_documents(documents)
    return documents