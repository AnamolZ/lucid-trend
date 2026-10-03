"""Asynchronous Celery task definitions for image synthesis and email newsletter distribution."""

import os
import re
import json
import logging
from celery import Celery
from dotenv import load_dotenv

from service.image_helper.get_image import huggingface_image
from service.emails.sender import send_bulk_emails, send_noreply_email
from service.mongodb.client import MongoDBService
from template.notify_subscriber import notify_subscriber_template
from config.logging_config import setup_logging

setup_logging()
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKENS") or os.getenv("HUGGING_FACE_TOKEN") or os.getenv("HF_TOKEN")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

celery_app = Celery(
    'lucidtrend',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kathmandu',
    enable_utc=True,
)

AUTHOR = {
    "name": "Anamol Dhakal",
    "role": "Backend System Developer",
    "avatar": "https://www.anamoldhakal.com.np/blog/assets/avatar-anamol-D1sVnQlG.jpg"
}
DEFAULT_IMAGE = "https://api.imghippo.com/files/dRXB7409pm.png"

@celery_app.task(bind=True, max_retries=3)
def generate_and_update_image_task(self, post_id: str, image_prompt: str, title: str) -> bool:
    """Synthesizes FLUX.1 visual assets across key rotation and reschedules backoff via Celery retry."""
    attempt_num = self.request.retries + 1
    logging.info(f"[ImageWorker] Initiated FLUX.1 task for post '{post_id}' (attempt {attempt_num}/4)...")

    if not image_prompt and title:
        image_prompt = (
            f"Cinematic digital illustration of {title}, clean 16:9 composition, high quality lighting"
        )

    if not image_prompt:
        logging.warning(f"[ImageWorker] No prompt available for '{post_id}'. Retaining default image.")
        return False

    # Attempt generation across active keys in this cycle without blocking worker on sleep
    image_url = huggingface_image(prompt=image_prompt, max_rounds=1, wait_seconds=0)

    if image_url:
        mongo_service = MongoDBService()
        mongo_service.update_post_image(post_id, image_url)
        logging.info(f"[ImageWorker] Successfully updated MongoDB post '{post_id}' with FLUX.1 image.")
        return True
    else:
        if self.request.retries < self.max_retries:
            logging.warning(
                f"[ImageWorker] All Hugging Face keys exhausted for '{post_id}'. Scheduling retry in 300s via Celery..."
            )
            raise self.retry(countdown=300)
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

def _format_article_html(item: dict) -> str:
    """Transforms raw markdown content into editorial HTML blocks with clickable links and code styling."""
    title = item.get("title", "Technical Update")
    category = item.get("category", ["Breaking News"])
    if isinstance(category, list):
        cat_str = category[1] if len(category) > 1 and category[1] != "Breaking News" else category[0]
    else:
        cat_str = str(category)
    cat_str = cat_str.split("|")[0].strip()

    description = item.get("description", "")
    content = item.get("content", "")

    # Extract dynamic takeaway if available from article content
    takeaway = "Direct architectural improvements and ecosystem implications for production codebases."
    if "## Final Takeaway" in content:
        parts = content.split("## Final Takeaway", 1)
        extracted = parts[1].strip().split("\n\n")[0].strip()
        if extracted:
            takeaway = re.sub(r"^[#\s*\-]+", "", extracted)
    elif description:
        takeaway = description

    formatted_sections = []
    if content:
        lines = content.strip().split("\n")
        in_list = False
        parsed_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_list:
                    parsed_lines.append("</ul>")
                    in_list = False
                continue

            if stripped.startswith("## ") or stripped.startswith("### "):
                if in_list:
                    parsed_lines.append("</ul>")
                    in_list = False
                heading_text = stripped.lstrip("#").strip()
                parsed_lines.append(f"<h3>{heading_text}</h3>")
            elif stripped.startswith("- ") or stripped.startswith("* ") or re.match(r"^\d+\.\s", stripped):
                if not in_list:
                    parsed_lines.append("<ul>")
                    in_list = True
                item_text = re.sub(r"^(?:[-*]|\d+\.)\s+", "", stripped)
                item_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", item_text)
                item_text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", item_text)
                item_text = re.sub(r"`(.*?)`", r'<code style="background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 13px;">\1</code>', item_text)
                item_text = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" style="color: #2563eb; text-decoration: underline;">\1</a>', item_text)
                parsed_lines.append(f"<li>{item_text}</li>")
            else:
                if in_list:
                    parsed_lines.append("</ul>")
                    in_list = False
                para_text = stripped
                para_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", para_text)
                para_text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", para_text)
                para_text = re.sub(r"`(.*?)`", r'<code style="background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 13px;">\1</code>', para_text)
                para_text = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" style="color: #2563eb; text-decoration: underline;">\1</a>', para_text)
                parsed_lines.append(f"<p>{para_text}</p>")

        if in_list:
            parsed_lines.append("</ul>")

        formatted_sections.append("\n".join(parsed_lines))
    elif description:
        formatted_sections.append(f"<p>{description}</p>")

    body_html = "\n".join(formatted_sections)

    return f"""
    <div class="article-entry">
        <span class="category-tag">{cat_str}</span>
        <h2 class="article-title">{title}</h2>
        <p class="article-summary">{description}</p>
        <div class="article-body">
            {body_html}
        </div>
        <div class="takeaway-box">
            <strong>Key Engineering Impact:</strong> {takeaway}
        </div>
    </div>
    """

@celery_app.task
def send_email_task(news_json_str: str) -> bool:
    """Dispatches high-deliverability text-only editorial briefings using bulk SMTP delivery."""
    mongo_service = MongoDBService()
    addresses = mongo_service.get_verified_subscribers()
    if not addresses:
        logging.info("[EmailWorker] No verified subscribers found.")
        return True

    news_json = json.loads(news_json_str)
    if not news_json:
        logging.info("[EmailWorker] No articles to dispatch.")
        return True

    first_title = news_json[0].get("title", "Daily Intelligence Briefing")
    subject = f"LucidTrend Intelligence: {first_title}"

    blocks = [_format_article_html(item) for item in news_json]
    news_content = "\n".join(blocks)

    email_entries = [
        (email, subject, notify_subscriber_template(subject, news_content, email))
        for email in addresses
    ]

    sent_count = send_bulk_emails(email_entries, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD)
    logging.info(f"[EmailWorker] Newsletter dispatch complete: {sent_count}/{len(addresses)} sent.")
    return True
