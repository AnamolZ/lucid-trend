import os
import re
import json
import logging
from celery import Celery
from dotenv import load_dotenv

from service.image_helper.get_image import huggingface_image, unsplash_image
from service.emails.sender import send_noreply_email
from service.mongodb.client import MongoDBService
from template.notify_subscriber import notify_subscriber_template
from config.logging_config import setup_logging

setup_logging()
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKEN")
UNSPLASH_IMAGE = os.getenv("UNSPLASH_IMAGE")
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
def generate_image_task(item):
    image_url = None
    
    # 1. Use pre-generated keyword and prompt from RootAgent (0 Gemini tokens consumed)
    keyword = item.get("image_keyword")
    generation_prompt = item.get("image_prompt")
    
    # 2. Local fallback if missing from schema
    if not keyword and item.get("title"):
        words = [w for w in re.findall(r"[A-Za-z0-9]+", item.get("title", "")) if len(w) > 2]
        keyword = " ".join(words[:2]) if len(words) >= 2 else "Technology News"

    if not generation_prompt and item.get("title"):
        generation_prompt = f"Cinematic digital illustration of {item.get('title')}, futuristic, high tech aesthetic, clean 16:9 composition"

    # 3. Fetch image via HuggingFace FLUX.1-schnell or Unsplash
    if generation_prompt and HUGGING_FACE_TOKEN:
        try:
            image_url = huggingface_image(HUGGING_FACE_TOKEN, generation_prompt)
        except Exception:
            pass

    if not image_url and keyword and UNSPLASH_IMAGE:
        try:
            image_url = unsplash_image(keyword, UNSPLASH_IMAGE)
        except Exception:
            pass

    if not image_url:
        image_url = DEFAULT_IMAGE

    return {
        **item,
        "image": image_url,
        "thumbnail": image_url,
        "author": AUTHOR
    }

@celery_app.task
def send_email_task(news_json_str):
    mongo_service = MongoDBService()
    addresses = mongo_service.get_verified_subscribers()
    if not addresses:
        logging.info("[Celery Worker] No verified subscribers found.")
        return True

    news_json = json.loads(news_json_str)
    if not news_json:
        logging.info("[Celery Worker] No articles to dispatch.")
        return True

    # High-CTR subject line from the leading headline
    first_title = news_json[0].get("title", "Daily Tech Update")
    subject = f"🔥 Tech Dispatch: {first_title}"

    # Clean HTML newsletter blocks directly from curated articles
    blocks = []
    for item in news_json:
        t = item.get("title", "Tech News")
        d = item.get("description", "") or item.get("content", "")[:350]
        blocks.append(f"<h2>{t}</h2>\n<p>{d}</p>")
    news_content = "\n".join(blocks)
    
    sent_count = 0
    for email in addresses:
        html_content = notify_subscriber_template(subject, news_content, email)
        if send_noreply_email(email, subject, html_content, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD):
            sent_count += 1

    logging.info(f"[Celery Worker] Newsletter dispatch complete: {sent_count}/{len(addresses)} sent.")
    return True
