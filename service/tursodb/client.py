"""Turso libSQL persistence service for managing articles and subscribers."""

import os
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

class TursoDBService:
    """Provides structured data access and persistence operations on Turso via HTTP Pipeline API."""

    def __init__(self, db_url: str = None, auth_token: str = None):
        raw_url = db_url or os.getenv("TURSO_DATABASE_URL")
        if raw_url:
            self.http_url = raw_url.replace("libsql://", "https://").rstrip("/") + "/v2/pipeline"
        else:
            self.http_url = None
        self.auth_token = auth_token or os.getenv("TURSO_AUTH_TOKEN")

    def execute_batch(self, statements: list) -> dict:
        """Executes a list of SQL statement dicts [{sql: '...', args: [...]}] against Turso pipeline."""
        if not self.http_url or not self.auth_token:
            logging.warning("[TursoDB] TURSO_DATABASE_URL or TURSO_AUTH_TOKEN not configured.")
            return {}

        requests_payload = []
        for stmt in statements:
            requests_payload.append({
                "type": "execute",
                "stmt": {
                    "sql": stmt["sql"],
                    "args": [{"type": "text", "value": str(arg) if arg is not None else None} for arg in stmt.get("args", [])]
                }
            })

        req = urllib.request.Request(
            self.http_url,
            data=json.dumps({"requests": requests_payload}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            logging.error(f"[TursoDB] Pipeline HTTP Error {e.code}: {err_body}")
            raise
        except Exception as e:
            logging.error(f"[TursoDB] Pipeline Execution Error: {e}")
            raise

    def execute(self, sql: str, args: list = None) -> dict:
        return self.execute_batch([{"sql": sql, "args": args or []}])

    def delete_older_than_days(self, days: int = 14) -> int:
        """Purges articles older than `days` based on published_at or created_at."""
        if not self.http_url:
            return 0
        cutoff_dt = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"[TursoDB] Purging posts older than {days} days (cutoff: {cutoff_dt})...")
        try:
            sql = "DELETE FROM posts WHERE created_at < ?;"
            self.execute(sql, [cutoff_dt])
            logging.info("[TursoDB] Purge executed.")
            return 1
        except Exception as e:
            logging.error(f"[TursoDB] Error purging old posts: {e}")
            return 0

    def insert_documents(self, documents: list, purge_older_than_days: int = 14) -> list:
        """Persists article documents into Turso 'posts' table."""
        if not self.http_url:
            return []

        if purge_older_than_days and purge_older_than_days > 0:
            try:
                self.delete_older_than_days(days=purge_older_than_days)
            except Exception as e:
                logging.warning(f"[TursoDB] Purge warning: {e}")

        if not documents:
            return []

        statements = []
        inserted_ids = []

        upsert_query = """
            INSERT INTO posts (
                id, title, slug, description, content,
                image, thumbnail, image_prompt, category, author, source, published_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                slug = excluded.slug,
                description = excluded.description,
                content = excluded.content,
                image = excluded.image,
                thumbnail = excluded.thumbnail,
                image_prompt = excluded.image_prompt,
                category = excluded.category,
                author = excluded.author,
                source = excluded.source,
                published_at = excluded.published_at;
        """

        for doc in documents:
            post_id = doc.get("id") or str(doc.get("_id"))
            slug = doc.get("slug") or post_id
            title = doc.get("title", "")
            description = doc.get("description", "")
            content = doc.get("content", "")
            image = doc.get("image", "")
            thumbnail = doc.get("thumbnail", "")
            image_prompt = doc.get("image_prompt") or ""
            category = json.dumps(doc.get("category", ["General"])) if isinstance(doc.get("category"), list) else str(doc.get("category") or "General")
            author = json.dumps(doc.get("author")) if isinstance(doc.get("author"), dict) else str(doc.get("author") or "")
            source = doc.get("source", "NewsPluk Editorial")
            now_iso = datetime.now(timezone.utc).isoformat()
            published_at = doc.get("published_at") or doc.get("date") or now_iso

            statements.append({
                "sql": upsert_query,
                "args": [
                    post_id, title, slug, description, content,
                    image, thumbnail, image_prompt, category, author, source, published_at
                ]
            })
            inserted_ids.append(post_id)

        try:
            self.execute_batch(statements)
            logging.info(f"[TursoDB] Successfully upserted {len(inserted_ids)} articles.")
            return inserted_ids
        except Exception as e:
            logging.error(f"[TursoDB] Batch insert error: {e}")
            return []

    def update_post_image(self, post_id: str, image_url: str):
        """Updates the image and thumbnail for a post."""
        if not self.http_url:
            return
        sql = "UPDATE posts SET image = ?, thumbnail = ? WHERE id = ?;"
        self.execute(sql, [image_url, image_url, post_id])
        logging.info(f"[TursoDB] Updated image for post '{post_id}'.")
    def remove_duplicate_posts(self, duplicate_ids: list) -> int:
        """Purges duplicate records from Turso database while preserving original records."""
        if not duplicate_ids:
            return 0

        statements = []
        for post_id in duplicate_ids:
            if not post_id:
                continue
            statements.append({
                "sql": "DELETE FROM posts WHERE id = ?",
                "args": [str(post_id)]
            })

        if not statements:
            return 0

        res = self.execute_batch(statements)
        logging.info(f"[TursoDB] Purged {len(statements)} duplicate posts from Turso.")
        return len(statements)

