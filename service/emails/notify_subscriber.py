"""Newsletter subscriber notification dispatcher via Celery background tasks."""

import json
import os
import logging
from service.tasks.tasks import send_email_task

def notify_subscribers(data_or_path, model=None, mongo_uri: str = None, smtp_server: str = None, smtp_user: str = None, smtp_password: str = None) -> bool:
    """Dispatches newsletter briefing task to background worker for verified subscribers."""
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
    logging.info(f"[NotifySubscribers] Queuing newsletter & mobile push dispatch for {len(news_data)} articles...")

    # 1. Dispatch Email Newsletter Task
    try:
        email_task = send_email_task.delay(news_json_str)
        logging.info("[NotifySubscribers] Queued email newsletter dispatch task via Celery.")
    except Exception as e:
        logging.warning(f"[NotifySubscribers] Failed to queue email task: {e}")

    # 2. Dispatch Mobile Push Notifications Task (Firebase FCM)
    try:
        from service.tasks.tasks import send_push_notifications_batch_task
        push_task = send_push_notifications_batch_task.delay(news_json_str)
        logging.info("[NotifySubscribers] Queued mobile push notification task via Celery.")
    except Exception as push_err:
        logging.warning(f"[NotifySubscribers] Celery push queue offline ({push_err}). Dispatching inline push...")
        try:
            from service.notifications.push_service import send_article_push
            for art in news_data:
                send_article_push(art)
        except Exception as inline_err:
            logging.error(f"[NotifySubscribers] Inline push dispatch failed: {inline_err}")

    return True