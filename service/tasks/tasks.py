"""Asynchronous Celery task definitions for image synthesis and email newsletter distribution."""

import os
import re
import logging
from celery import Celery
from dotenv import load_dotenv

from service.image_helper.get_image import huggingface_image
from service.emails.sender import send_bulk_emails, send_noreply_email
from service.mongodb.client import MongoDBService
from service.tursodb.client import TursoDBService
from template.notify_subscriber import notify_subscriber_template
from config.logging_config import setup_logging

setup_logging()
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKENS") or os.getenv("HUGGING_FACE_TOKEN") or os.getenv("HF_TOKEN")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_USER = os.getenv("SMTP_USER")
AUTHOR = {
    "name": "Anamol Dhakal",
    "role": "Backend System Developer",
    "avatar": "https://www.anamoldhakal.com.np/images/about-2.jpg"
}
DEFAULT_IMAGE = "https://api.imghippo.com/files/dRXB7409pm.png"

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
)

@celery_app.task(bind=True, max_retries=3)
def generate_and_update_image_task(self, post_id: str, image_prompt: str = None, title: str = None, description: str = None, category: list = None) -> bool:
    """Synthesizes high-precision FLUX visual assets and updates Turso & MongoDB in full uncompressed quality."""
    attempt_num = self.request.retries + 1
    logging.info(f"[ImageWorker] Initiated FLUX task for post '{post_id}' (attempt {attempt_num}/4)...")

    image_url = huggingface_image(
        prompt=image_prompt,
        title=title,
        description=description,
        category=category,
        wait_seconds=0
    )

    if image_url:
        # 1. Update Turso DB (Serving - Full Original Quality)
        try:
            turso_service = TursoDBService()
            turso_service.update_post_image(post_id, image_url)
            logging.info(f"[ImageWorker] Successfully updated Turso DB post '{post_id}' with FLUX image.")
        except Exception as turso_err:
            logging.error(f"[ImageWorker] Turso update error for '{post_id}': {turso_err}")

        # 2. Update MongoDB (Backup - Full Original Quality)
        try:
            mongo_service = MongoDBService()
            mongo_service.update_post_image(post_id, image_url)
            logging.info(f"[ImageWorker] Successfully updated MongoDB post '{post_id}' with FLUX image.")
        except Exception as mongo_err:
            logging.error(f"[ImageWorker] MongoDB update error for '{post_id}': {mongo_err}")

        return True
    else:
        if self.request.retries < self.max_retries:
            logging.warning(
                f"[ImageWorker] Image generation pending for '{post_id}'. Rescheduling retry in 60s..."
            )
            raise self.retry(countdown=60)
        else:
            logging.error(f"[ImageWorker] All retries exhausted for '{post_id}'. Retaining default image.")
            return False

@celery_app.task
def generate_image_task(item: dict) -> dict:
    """Synchronous fallback task for single-article image generation."""
    generation_prompt = item.get("image_prompt")
    if not generation_prompt and item.get("title"):
        generation_prompt = (
            f"Cinematic digital illustration of {item.get('title')}, futuristic, clean 16:9 composition"
        )

    image_url = None
    if generation_prompt and HUGGING_FACE_TOKEN:
        try:
            image_url = huggingface_image(prompt=generation_prompt, max_rounds=1, wait_seconds=0)
        except Exception as e:
            logging.warning(f"[Tasks] Image generation error: {e}")

    if not image_url:
        image_url = DEFAULT_IMAGE

    return {
        **item,
        "image": image_url,
        "thumbnail": image_url,
        "author": AUTHOR
    }

@celery_app.task
def send_email_task(news_json_str: str) -> bool:
    """Dispatches high-deliverability editorial briefings using bulk SMTP delivery."""
    mongo_service = MongoDBService()
    addresses = mongo_service.get_verified_subscribers()
    if not addresses:
        logging.info("[EmailWorker] No verified subscribers found.")
        return True

    try:
        articles = json.loads(news_json_str)
        if not isinstance(articles, list):
            logging.error("[EmailWorker] Invalid payload format. Expected JSON array.")
            return False

        html_content = notify_subscriber_template(articles)
        subject = f"NewsPluk Technical Dispatch: {articles[0].get('title', 'Daily Briefing')[:50]}"
        success = send_bulk_emails(addresses, subject, html_content)
        if success:
            logging.info(f"[EmailWorker] Successfully dispatched dispatch to {len(addresses)} subscribers.")
        else:
            logging.error("[EmailWorker] Email dispatch failed.")
        return success
    except Exception as e:
        logging.error(f"[EmailWorker] Error processing email task: {e}")
        return False
@celery_app.task
def send_push_notifications_batch_task(news_json_str: str) -> bool:
    """Dispatches high-priority Firebase FCM push notifications for published articles."""
    try:
        from service.notifications.push_service import send_article_push
        articles = json.loads(news_json_str)
        if not isinstance(articles, list):
            logging.error("[PushWorker] Invalid payload format. Expected JSON array.")
            return False

        success_count = 0
        for art in articles:
            if send_article_push(art):
                success_count += 1
        logging.info(f"[PushWorker] Successfully dispatched FCM push for {success_count}/{len(articles)} articles.")
        return success_count > 0
    except Exception as e:
        logging.error(f"[PushWorker] Error processing push notification batch task: {e}")
        return False

