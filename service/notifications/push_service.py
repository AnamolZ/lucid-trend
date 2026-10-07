"""Firebase Cloud Messaging (FCM) push notification service for mobile dispatch broadcasting."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

_firebase_initialized = False


def init_firebase() -> bool:
    """Initializes the Firebase Admin SDK using service account credentials."""
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            _firebase_initialized = True
            return True

        # Check candidate locations for service account key
        custom_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        candidates = []
        if custom_path:
            candidates.append(custom_path if os.path.isabs(custom_path) else os.path.join(base_dir, custom_path))
        candidates.extend([
            os.path.join(base_dir, "firebase-service-account.json"),
            os.path.join(base_dir, "newspluk-firebase-adminsdk-fbsvc-297b860de4.json"),
            os.path.join(os.getcwd(), "firebase-service-account.json"),
        ])

        key_path = next((p for p in candidates if os.path.exists(p)), None)
        if not key_path:
            logging.warning("[Firebase] Service account JSON not found. Mobile push notifications disabled.")
            return False

        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logging.info(f"[Firebase] Initialized Firebase Admin SDK successfully with '{os.path.basename(key_path)}'.")
        return True

    except Exception as e:
        logging.error(f"[Firebase] Failed to initialize Firebase Admin SDK: {e}")
        return False


def send_push_notification(title: str, body: str = "", post_id: str = None, topic: str = None) -> bool:
    """Broadcasts a high-priority push notification to a Firebase topic (default: 'all_news')."""
    if not init_firebase():
        return False

    try:
        from firebase_admin import messaging

        target_topic = topic or os.getenv("FIREBASE_NOTIFICATION_TOPIC", "all_news")
        post_link = f"/{post_id}" if post_id else "/"

        message = messaging.Message(
            topic=target_topic,
            notification=messaging.Notification(
                title="NewsPluk | New Dispatch Published",
                body=title or body or "New technical dispatch published."
            ),
            data={
                "id": str(post_id or ""),
                "link": post_link
            },
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="dispatches",
                    sound="default",
                    priority="high"
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default"
                    )
                )
            )
        )

        response = messaging.send(message)
        logging.info(f"[Firebase FCM] Successfully broadcasted push notification for post '{post_id}' (Message ID: {response}).")
        return True

    except Exception as e:
        logging.error(f"[Firebase FCM] Failed to dispatch push notification: {e}")
        return False


def send_article_push(article: dict) -> bool:
    """Dispatches a push notification corresponding to an article dictionary."""
    if not article or not isinstance(article, dict):
        return False

    title = article.get("title", "Breaking Technology Dispatch")
    post_id = article.get("id") or str(article.get("_id", ""))
    description = article.get("description", "")

    return send_push_notification(title=title, body=description, post_id=post_id)
