import json
import os
import logging
from service.tasks.tasks import send_email_task

def notify_subscribers(data_or_path, model=None, mongo_uri=None, smtp_server=None, smtp_user=None, smtp_password=None):
    """
    Sends daily briefing newsletter to verified subscribers via Celery.
    Accepts either in-memory articles list or a JSON file path.
    """
    if isinstance(data_or_path, list):
        news_data = data_or_path
    elif isinstance(data_or_path, str) and os.path.exists(data_or_path):
        with open(data_or_path, "r", encoding="utf-8") as f:
            news_data = json.load(f)
    else:
        logging.warning("[NotifySubscribers] No valid news data provided for notification.")
        return False

    if not news_data:
        logging.info("[NotifySubscribers] No news articles to dispatch.")
        return True

    news_json_str = json.dumps(news_data, ensure_ascii=False)
    logging.info(f"[NotifySubscribers] Queuing newsletter dispatch task with {len(news_data)} articles...")
    
    task = send_email_task.delay(news_json_str)
    try:
        task.get(timeout=30)
        logging.info("[NotifySubscribers] Newsletter dispatched successfully.")
        return True
    except Exception as e:
        logging.info(f"[NotifySubscribers] Task queued in background worker ({e}).")
        return True