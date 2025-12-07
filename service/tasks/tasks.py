import os
import json
from celery import Celery
from dotenv import load_dotenv
from pymongo import MongoClient
from google.generativeai import GenerativeModel, configure

from service.image_helper.get_image import huggingface_image, unsplash_image
from service.data_cleaning.gemini import image_suggestion, image_generation_prompt, email_title, build_content_with_gemini
from service.emails.sender import send_noreply_email
from service.mongodb.fetch_emails import get_verified_emails
from template.notify_subscriber import notify_subscriber_template

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKEN")
UNSPLASH_IMAGE = os.getenv("UNSPLASH_IMAGE")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

celery_app = Celery(
    'lucidtrend',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
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
    content = item.get("content", "")
    image_url = None
    
    if content:
        try:
            configure(api_key=GOOGLE_API_KEY)
            model = GenerativeModel("gemini-2.5-flash")
            
            keyword = image_suggestion(model, content)
            if keyword:
                try:
                    generation_prompt = image_generation_prompt(model, content)
                    if generation_prompt:
                        image_url = huggingface_image(HUGGING_FACE_TOKEN, generation_prompt)
                except Exception:
                    pass

                if not image_url:
                    try:
                        image_url = unsplash_image(keyword, UNSPLASH_IMAGE)
                    except Exception:
                        pass
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
    configure(api_key=GOOGLE_API_KEY)
    model = GenerativeModel("gemini-2.5-flash")
    news_json = json.loads(news_json_str)
    
    addresses = get_verified_emails(MONGO_URI)
    subject = email_title(model)
    news_content = build_content_with_gemini(news_json, model)
    
    for email in addresses:
        html_content = notify_subscriber_template(subject, news_content, email)
        send_noreply_email(email, subject, html_content, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD)
