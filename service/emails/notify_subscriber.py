
import json
from celery import group
from service.tasks.tasks import send_email_task

def notify_subscribers(model, MONGO_URI, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD):
    with open("service/blog/extracted_data.json", "r", encoding="utf-8") as f:
        news_json = json.load(f)
    
    news_json_str = json.dumps(news_json)
    
    send_email_task.delay(news_json_str)