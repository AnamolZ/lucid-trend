import os
import re
import json
import logging
from celery import Celery
from dotenv import load_dotenv

from service.image_helper.get_image import huggingface_image
from service.emails.sender import send_noreply_email
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

@celery_app.task
def generate_and_update_image_task(post_id: str, image_prompt: str, title: str):
    """
    Asynchronous background image worker:
    1. Attempts FLUX.1 generation across all keys.
    2. If all fail, waits 5 minutes before retrying (up to 3 rounds).
    3. On success, updates MongoDB document in-place.
    4. If permanently exhausted, retains DEFAULT_IMAGE.
    """
    logging.info(f"[ImageWorker] Initiated FLUX.1 generation task for post '{post_id}'...")

    if not image_prompt and title:
        image_prompt = (
            f"Cinematic digital illustration of {title}, futuristic, high tech aesthetic, clean 16:9 composition"
        )

    if not image_prompt:
        logging.warning(f"[ImageWorker] No prompt available for '{post_id}'. Retaining default image.")
        return False

    image_url = huggingface_image(prompt=image_prompt, max_rounds=3, wait_seconds=300)

    if image_url:
        mongo_service = MongoDBService()
        mongo_service.update_post_image(post_id, image_url)
        logging.info(f"[ImageWorker] Successfully updated MongoDB post '{post_id}' with FLUX.1 image.")
        return True
    else:
        logging.warning(
            f"[ImageWorker] Failed to synthesize image for '{post_id}' after 3 rounds. Retaining default image."
        )
        return False

@celery_app.task
def generate_image_task(item):
    """
    Synchronous fallback for image synthesis.
    """
    generation_prompt = item.get("image_prompt")
    if not generation_prompt and item.get("title"):
        generation_prompt = (
            f"Cinematic digital illustration of {item.get('title')}, futuristic, high tech aesthetic, clean 16:9 composition"
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
    """Transforms raw markdown content into clean, editorial HTML blocks for email delivery."""
    title = item.get("title", "Technical Update")
    category = item.get("category", ["Breaking News"])
    cat_str = category[0] if isinstance(category, list) and category else str(category)
    description = item.get("description", "")
    content = item.get("content", "")

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
            elif stripped.startswith("- ") or stripped.startswith("* "):
                if not in_list:
                    parsed_lines.append("<ul>")
                    in_list = True
                item_text = stripped[2:].strip()
                item_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", item_text)
                parsed_lines.append(f"<li>{item_text}</li>")
            else:
                if in_list:
                    parsed_lines.append("</ul>")
                    in_list = False
                para_text = stripped
                para_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", para_text)
                para_text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", para_text)
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
            <strong>Key Engineering Impact:</strong> Verified architectural updates and ecosystem implications for active codebases.
        </div>
    </div>
    """

@celery_app.task
def send_email_task(news_json_str):
    """
    Sends a professional, text-only editorial newsletter to verified subscribers.
    Does not include images.
    """
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

    # Build clean, high-signal editorial blocks (text only)
    blocks = [_format_article_html(item) for item in news_json]
    news_content = "\n".join(blocks)

    sent_count = 0
    for email in addresses:
        html_content = notify_subscriber_template(subject, news_content, email)
        if send_noreply_email(email, subject, html_content, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD):
            sent_count += 1

    logging.info(f"[EmailWorker] Newsletter dispatch complete: {sent_count}/{len(addresses)} sent.")
    return True
