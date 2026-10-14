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
    "avatar": "https://www.anamoldhakal.com.np/images/about-2.jpg"
}
DEFAULT_IMAGE = "https://api.imghippo.com/files/dRXB7409pm.png"

@celery_app.task(bind=True, max_retries=3)
def generate_and_update_image_task(self, post_id: str, image_prompt: str = None, title: str = None, description: str = None, category: list = None) -> bool:
    """Synthesizes high-precision FLUX visual assets via Cloudflare/Pollinations cascade and updates MongoDB."""
    attempt_num = self.request.retries + 1
    logging.info(f"[ImageWorker] Initiated FLUX task for post '{post_id}' (attempt {attempt_num}/4)...")

    image_url = huggingface_image(
        prompt=image_prompt,
        title=title,
        description=description,
        category=category,
        max_rounds=1,
        wait_seconds=0
    )

    if image_url:
        mongo_service = MongoDBService()
        mongo_service.update_post_image(post_id, image_url)
        logging.info(f"[ImageWorker] Successfully updated MongoDB post '{post_id}' with FLUX image.")

        try:
            from service.neondb.client import NeonDBService
            neon_service = NeonDBService()
            neon_service.update_post_image(post_id, image_url)
            logging.info(f"[ImageWorker] Successfully updated NeonDB post '{post_id}' with FLUX image.")
        except Exception as neon_err:
            logging.warning(f"[ImageWorker] NeonDB image update warning for '{post_id}': {neon_err}")

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

def _format_summary_bullet(item: dict) -> str:
    """Creates a concise 1-line bullet for the top Executive Summary card."""
    title = item.get("title", "Update").strip()
    short_title = title.split(":")[0].strip() if ":" in title else title
    if len(short_title) > 35:
        short_title = short_title[:35].rsplit(" ", 1)[0]

    content = item.get("content", "")
    description = item.get("description", "").strip()

    takeaway = description
    if "## Final Takeaway" in content:
        parts = content.split("## Final Takeaway", 1)
        extracted = parts[1].strip().split("\n\n")[0].strip()
        if extracted:
            takeaway = re.sub(r"^[#\s*\-]+", "", extracted)

    # Clean takeaway and pick first sentence
    takeaway = re.sub(r"[*`\[\]]", "", takeaway).strip()
    first_sentence = takeaway.split(". ")[0].strip()
    if not first_sentence.endswith("."):
        first_sentence += "."

    return f"""
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 10px;">
        <tr>
            <td width="18" valign="top" style="font-size: 14px; color: #1a73e8; line-height: 1.5;">&bull;</td>
            <td style="font-size: 13.5px; line-height: 1.55; color: #3c4043;">
                <strong style="color: #202124; font-weight: 600;">{short_title}:</strong> {first_sentence}
            </td>
        </tr>
    </table>
    """

def _format_article_html(item: dict, is_last: bool = False) -> str:
    """Transforms article into a clean, Google-styled editorial briefing block without tags."""
    title = item.get("title", "Technical Update")
    description = item.get("description", "").strip()
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

    # Format concise paragraph with clean inline formatting
    clean_summary = description
    clean_summary = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", clean_summary)
    clean_summary = re.sub(r"\*(.*?)\*", r"<em>\1</em>", clean_summary)
    clean_summary = re.sub(r"`(.*?)`", r'<code style="background: #f1f3f4; padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 13px; color: #202124;">\1</code>', clean_summary)
    clean_summary = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" style="color: #1a73e8; text-decoration: none;">\1</a>', clean_summary)

    clean_takeaway = takeaway
    clean_takeaway = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", clean_takeaway)
    clean_takeaway = re.sub(r"\*(.*?)\*", r"<em>\1</em>", clean_takeaway)
    clean_takeaway = re.sub(r"`(.*?)`", r'<code style="background: #f1f3f4; padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 13px; color: #202124;">\1</code>', clean_takeaway)
    clean_takeaway = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" style="color: #1a73e8; text-decoration: none;">\1</a>', clean_takeaway)

    border_bottom = "border-bottom: 1px solid #e8eaed; padding-bottom: 30px; margin-bottom: 30px;" if not is_last else "margin-bottom: 0;"

    return f"""
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="{border_bottom}">
        <tr>
            <td>
                <h2 class="article-headline" style="margin: 0 0 10px 0; font-size: 19px; font-weight: 600; color: #202124; line-height: 1.35; letter-spacing: -0.2px;">
                    {title}
                </h2>
                <p style="margin: 0 0 14px 0; font-size: 14px; line-height: 1.65; color: #3c4043;">
                    {clean_summary}
                </p>
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8f9fa; border-left: 3px solid #1a73e8; border-radius: 0 6px 6px 0;">
                    <tr>
                        <td style="padding: 12px 16px; font-size: 13.5px; line-height: 1.55; color: #3c4043;">
                            <span style="color: #1a73e8; font-weight: 700; margin-right: 4px;">Impact:</span>
                            {clean_takeaway}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    """

@celery_app.task
def send_email_task(news_json_str: str) -> bool:
    """Dispatches high-deliverability editorial briefings using bulk SMTP delivery."""
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
    subject = f"Your Daily Brief - NewsPluk: {first_title}"

    # Generate top Executive Summary bullets
    summary_bullets = [_format_summary_bullet(item) for item in news_json]
    summary_content = "\n".join(summary_bullets)

    # Generate full article blocks
    total_articles = len(news_json)
    blocks = [_format_article_html(item, is_last=(i == total_articles - 1)) for i, item in enumerate(news_json)]
    news_content = "\n".join(blocks)

    email_entries = [
        (email, subject, notify_subscriber_template(subject, news_content, email, summary_content))
        for email in addresses
    ]

    sent_count = send_bulk_emails(email_entries, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD)
    logging.info(f"[EmailWorker] Newsletter dispatch complete: {sent_count}/{len(addresses)} sent.")
    return True

@celery_app.task
def send_push_notification_task(item: dict) -> bool:
    """Dispatches a mobile push notification via Firebase FCM for an individual article."""
    from service.notifications.push_service import send_article_push
    logging.info(f"[PushWorker] Broadcasting FCM push notification for post '{item.get('id')}'...")
    return send_article_push(item)

@celery_app.task
def send_push_notifications_batch_task(news_json_str: str) -> int:
    """Dispatches mobile push notifications to Firebase topic 'all_news' for a batch of published articles."""
    from service.notifications.push_service import send_article_push
    try:
        articles = json.loads(news_json_str) if isinstance(news_json_str, str) else news_json_str
        sent = 0
        for art in articles:
            logging.info(f"[PushWorker] Broadcasting FCM push notification for '{art.get('title')}'...")
            if send_article_push(art):
                sent += 1
        logging.info(f"[PushWorker] Mobile push broadcast complete: {sent}/{len(articles)} dispatches sent.")
        return sent
    except Exception as e:
        logging.error(f"[PushWorker] Batch push dispatch failed: {e}")
        return 0
