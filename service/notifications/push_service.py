"""Firebase Cloud Messaging (FCM) push notification service for mobile dispatch broadcasting."""

import os
import re
import json
import base64
import logging
import urllib.request
import urllib.error
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

        # 1. Check for raw or Base64 JSON in FIREBASE_SERVICE_ACCOUNT env var
        raw_env = (
            os.getenv("FIREBASE_SERVICE_ACCOUNT")
            or os.getenv("FIREBASE_SERVICE_ACCOUNT_B64")
            or os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64")
        )
        if raw_env:
            raw_str = str(raw_env).strip()
            account_info = None

            # Attempt A: Direct JSON string
            if raw_str.startswith("{") and raw_str.endswith("}"):
                try:
                    account_info = json.loads(raw_str)
                except Exception as parse_err:
                    logging.warning(f"[Firebase] Failed to parse raw FIREBASE_SERVICE_ACCOUNT JSON: {parse_err}")

            # Attempt B: Base64-encoded JSON string
            if not account_info:
                try:
                    decoded = base64.b64decode(raw_str).decode("utf-8")
                    if decoded.strip().startswith("{"):
                        account_info = json.loads(decoded)
                except Exception:
                    pass

            if account_info and isinstance(account_info, dict) and "project_id" in account_info:
                cred = credentials.Certificate(account_info)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                logging.info("[Firebase] Initialized Firebase Admin SDK successfully from FIREBASE_SERVICE_ACCOUNT environment secret.")
                return True

        # 2. Check candidate filesystem locations for service account key file
        custom_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        candidates = []
        if custom_path:
            candidates.append(custom_path if os.path.isabs(custom_path) else os.path.join(base_dir, custom_path))

        candidates.extend([
            os.path.join(base_dir, "firebase-service-account.json"),
            os.path.join(base_dir, "newspluk-firebase-adminsdk-fbsvc-297b860de4.json"),
            os.path.join(os.getcwd(), "firebase-service-account.json"),
            os.path.join(base_dir, "..", "news-pluk", "api", "newspluk-firebase-adminsdk-fbsvc-297b860de4.json"),
            os.path.join(base_dir, "..", "news-pluk", "newspluk-firebase-adminsdk-fbsvc-297b860de4.json"),
        ])

        key_path = next((p for p in candidates if os.path.exists(p)), None)
        if key_path:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logging.info(f"[Firebase] Initialized Firebase Admin SDK successfully with '{os.path.basename(key_path)}'.")
            return True

        logging.warning("[Firebase] Service account JSON not found in environment or filesystem. Direct SDK push disabled.")
        return False

    except Exception as e:
        logging.error(f"[Firebase] Failed to initialize Firebase Admin SDK: {e}")
        return False


def _send_push_via_api_webhook(title: str, post_id: str = None, extra_data: dict = None) -> bool:
    """Fallback dispatcher: Invokes the NewsPluk Edge /api/notify serverless endpoint."""
    api_url = (os.getenv("NOTIFY_API_URL") or "").strip() or "https://newspluk.com/api/notify"
    api_key = (os.getenv("NOTIFY_API_KEY") or "").strip() or "newspluk_notify_secret_2026"

    payload = {
        "id": str(post_id or ""),
        "postId": str(post_id or ""),
        "post_id": str(post_id or ""),
        "title": (title or "Breaking Technology Dispatch")[:120],
        "category": "News"
    }
    if extra_data and isinstance(extra_data, dict):
        payload.update(extra_data)

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "User-Agent": "NewsPluk-Backend-Dispatcher/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                logging.info(f"[PushWebhook] Dispatched notification via edge webhook for post '{post_id}'.")
                return True
            else:
                logging.warning(f"[PushWebhook] Edge webhook returned status {resp.status}.")
                return False
    except Exception as err:
        logging.warning(f"[PushWebhook] Fallback webhook dispatch failed: {err}")
        return False


def send_push_notification(title: str, body: str = "", post_id: str = None, topic: str = None, extra_data: dict = None) -> bool:
    """Broadcasts a high-priority push notification to a Firebase topic (default: 'all_news') with lean rich payload."""
    if init_firebase():
        try:
            from firebase_admin import messaging

            target_topic = topic or os.getenv("FIREBASE_NOTIFICATION_TOPIC", "all_news")
            post_link = f"/{post_id}" if post_id else "/"

            fcm_data = {
                "id": str(post_id or ""),
                "postId": str(post_id or ""),
                "link": post_link,
                "title": str(title or "")[:120],
                "body": str(body or title or "")[:120],
            }
            if extra_data and isinstance(extra_data, dict):
                for k, v in extra_data.items():
                    if v is not None:
                        val_str = str(v)
                        # STRICT SAFEGUARD: Never allow any single field (e.g. base64 or markdown)
                        # to exceed 250 characters and blow past the FCM 4096-byte limit
                        if len(val_str) > 250:
                            val_str = val_str[:250]
                        fcm_data[str(k)] = val_str

            # Strict guardrail: calculate total payload byte size (must remain well under 4096 bytes)
            total_bytes = sum(len(k.encode("utf-8")) + len(v.encode("utf-8")) for k, v in fcm_data.items())
            if total_bytes > 3000:
                fcm_data["description"] = fcm_data.get("description", "")[:100]
                fcm_data["excerpt"] = fcm_data.get("excerpt", "")[:100]

            post_tag = str(post_id or "").strip()
            message = messaging.Message(
                topic=target_topic,
                notification=messaging.Notification(
                    title="NewsPluk | New Dispatch Published",
                    body=(title or body or "New technical dispatch published.")[:120]
                ),
                data=fcm_data,
                android=messaging.AndroidConfig(
                    priority="high",
                    collapse_key=post_tag if post_tag else None,
                    notification=messaging.AndroidNotification(
                        channel_id="dispatches",
                        tag=post_tag if post_tag else None,
                        sound="default",
                        priority="high",
                        default_vibrate_timings=True,
                        visibility="public"
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
            logging.error(f"[Firebase FCM] Direct push dispatch failed: {e}. Attempting webhook fallback...")

    # Fallback to web API notify endpoint if SDK credentials are not present or failed
    return _send_push_via_api_webhook(title=title, post_id=post_id, extra_data=extra_data)


def send_article_push(article: dict) -> bool:
    """Dispatches a high-fidelity lean push notification corresponding to an article dictionary."""
    if not article or not isinstance(article, dict):
        return False

    post_id = article.get("id") or str(article.get("_id", ""))
    title = str(article.get("title", "Breaking Technology Dispatch"))[:120]
    raw_desc = str(article.get("description", "") or article.get("excerpt", ""))
    clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()
    clean_desc = " ".join(clean_desc.split())
    description = clean_desc[:200]

    raw_category = article.get("category", ["General"])
    category_str = str(raw_category[0] if isinstance(raw_category, list) and raw_category else (raw_category or "News"))[:30]

    # CRITICAL FIX: Turso stores raw base64 data URIs (50KB-200KB) in the image column!
    # Under NO circumstance send base64 data URIs to FCM (causes 'Message is too large' 4KB error).
    # Always resolve to the ultra-compact CDN image URL (/images/<post_id>.jpg).
    raw_img = article.get("image") or article.get("thumbnail") or ""
    if raw_img and (str(raw_img).startswith("data:") or len(str(raw_img)) > 200):
        img = f"https://newspluk.com/images/{post_id}.jpg" if post_id else ""
    elif raw_img and str(raw_img).startswith("/"):
        img = f"https://newspluk.com{raw_img}"
    elif raw_img and str(raw_img).startswith("http"):
        img = str(raw_img)[:200]
    else:
        img = f"https://newspluk.com/images/{post_id}.jpg" if post_id else ""

    raw_author = article.get("author")
    if isinstance(raw_author, dict):
        author_name = str(raw_author.get("name", "Anamol Dhakal"))[:50]
        author_role = str(raw_author.get("role", "Backend System Developer"))[:50]
    else:
        author_name = str(raw_author or "Anamol Dhakal")[:50]
        author_role = "Backend System Developer"

    read_time = str(article.get("readingTime") or article.get("reading_time") or article.get("readTime") or "3 min")[:15]
    pub_date = str(article.get("published_at") or article.get("date") or article.get("created_at") or "")[:35]

    extra_data = {
        "description": description,
        "excerpt": description,
        "category": category_str,
        "image": img,
        "thumbnail": img,
        "readingTime": read_time,
        "readTime": read_time,
        "published_at": pub_date,
        "date": pub_date,
        "authorName": author_name,
        "authorRole": author_role,
    }

    return send_push_notification(title=title, body=description, post_id=post_id, extra_data=extra_data)


def send_latest_dispatches_push(limit: int = 2) -> int:
    """Fetches the most recently inserted Turso dispatches and broadcasts rich notifications."""
    try:
        from service.tursodb.client import TursoDBService
        turso = TursoDBService()
        posts = turso.fetch_recent_posts_for_export(limit=limit)
        if not posts:
            logging.warning("[PushService] No recent posts found to notify.")
            return 0
        count = 0
        for p in posts:
            if send_article_push(p):
                count += 1
        logging.info(f"[PushService] Broadcasted push for {count}/{len(posts)} recent dispatches.")
        return count
    except Exception as e:
        logging.error(f"[PushService] Error broadcasting latest dispatches: {e}")
        return 0
