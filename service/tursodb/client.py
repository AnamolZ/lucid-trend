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

    def delete_older_than_days(self, days: int = 90) -> int:
        """Purges articles older than `days` based on published_at or created_at."""
        if not self.http_url:
            return 0
        cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cutoff_space = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"[TursoDB] Purging posts older than {days} days (cutoff: {cutoff_iso})...")
        try:
            sql = "DELETE FROM posts WHERE published_at < ? OR (published_at IS NULL AND created_at < ?);"
            res = self.execute(sql, [cutoff_iso, cutoff_space])
            affected = res.get("results", [{}])[0].get("response", {}).get("result", {}).get("affected_row_count", 0)
            logging.info(f"[TursoDB] Purge executed: {affected} expired articles removed.")
            return affected
        except Exception as e:
            logging.error(f"[TursoDB] Error purging old posts: {e}")
            return 0

    def insert_documents(self, documents: list, purge_older_than_days: int = None) -> list:
        """Persists article documents into Turso 'posts' table."""
        if not self.http_url:
            return []

        if purge_older_than_days is None:
            try:
                purge_older_than_days = int(os.getenv("RETENTION_DAYS", "90"))
            except Exception:
                purge_older_than_days = 90

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
                image, thumbnail, image_prompt, audio_url, category, author, source, published_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                slug = excluded.slug,
                description = excluded.description,
                content = excluded.content,
                image = excluded.image,
                thumbnail = excluded.thumbnail,
                image_prompt = excluded.image_prompt,
                audio_url = CASE WHEN excluded.audio_url != '' THEN excluded.audio_url ELSE posts.audio_url END,
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
            audio_url = doc.get("audio_url") or ""
            category = json.dumps(doc.get("category", ["General"])) if isinstance(doc.get("category"), list) else str(doc.get("category") or "General")
            author = json.dumps(doc.get("author")) if isinstance(doc.get("author"), dict) else str(doc.get("author") or "")
            source = doc.get("source", "NewsPluk Editorial")
            now_iso = datetime.now(timezone.utc).isoformat()
            published_at = doc.get("published_at") or doc.get("date") or now_iso

            statements.append({
                "sql": upsert_query,
                "args": [
                    post_id, title, slug, description, content,
                    image, thumbnail, image_prompt, audio_url, category, author, source, published_at
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

    def update_post_audio(self, post_id: str, audio_url: str):
        """Updates the audio stream URL for a post."""
        if not self.http_url:
            return
        sql = "UPDATE posts SET audio_url = ? WHERE id = ?;"
        self.execute(sql, [audio_url, post_id])
        logging.info(f"[TursoDB] Updated audio_url for post '{post_id}'.")

    def fetch_all_posts(self) -> list:
        """Retrieves lightweight article metadata (id, title, description) for duplicate detection."""
        if not self.http_url:
            return []
        sql = "SELECT id, title, description FROM posts ORDER BY published_at DESC LIMIT 100;"
        res = self.execute(sql)
        posts = []
        try:
            results = res.get("results", [])
            if results:
                rows = results[0].get("response", {}).get("result", {}).get("rows", [])
                cols = [c["name"] for c in results[0].get("response", {}).get("result", {}).get("cols", [])]
                for row in rows:
                    post_dict = {}
                    for col_idx, col_name in enumerate(cols):
                        val_obj = row[col_idx]
                        post_dict[col_name] = val_obj.get("value") if isinstance(val_obj, dict) else val_obj
                    posts.append(post_dict)
        except Exception as e:
            logging.error(f"[TursoDB] Error fetching posts: {e}")
        logging.info(f"[TursoDB] Fetched {len(posts)} existing posts.")
        return posts

    def fetch_recent_posts_for_export(self, limit: int = 750) -> list:
        """Retrieves full article objects sorted by published_at DESC for static JSON baking."""
        if not self.http_url:
            return []
        sql = """
            SELECT id, title, slug, description, content, image, thumbnail,
                   image_prompt, audio_url, category, author, source, published_at, created_at
            FROM posts
            ORDER BY published_at DESC, id DESC
            LIMIT ?;
        """
        res = self.execute(sql, [limit])
        posts = []
        try:
            results = res.get("results", [])
            if results:
                rows = results[0].get("response", {}).get("result", {}).get("rows", [])
                cols = [c["name"] for c in results[0].get("response", {}).get("result", {}).get("cols", [])]
                for row in rows:
                    post_dict = {}
                    for col_idx, col_name in enumerate(cols):
                        val_obj = row[col_idx]
                        val = val_obj.get("value") if isinstance(val_obj, dict) else val_obj
                        if col_name in ("category", "author") and isinstance(val, str) and (val.startswith("[") or val.startswith("{")):
                            try:
                                post_dict[col_name] = json.loads(val)
                            except Exception:
                                post_dict[col_name] = val
                        else:
                            post_dict[col_name] = val
                    posts.append(post_dict)
        except Exception as e:
            logging.error(f"[TursoDB] Error fetching posts for export: {e}")
        return posts

    def get_verified_subscribers(self) -> list:
        """Queries and returns list of verified subscriber email addresses from Turso."""
        if not self.http_url:
            return []
        sql = "SELECT email FROM notification_addresses WHERE is_verified = 1;"
        try:
            res = self.execute(sql)
            results = res.get("results", [])
            emails = []
            if results:
                rows = results[0].get("response", {}).get("result", {}).get("rows", [])
                for r in rows:
                    if r and len(r) > 0:
                        val = r[0].get("value") if isinstance(r[0], dict) else r[0]
                        if val:
                            emails.append(str(val))
            logging.info(f"[TursoDB] Found {len(emails)} verified subscribers.")
            return emails
        except Exception as e:
            logging.error(f"[TursoDB] Error fetching verified subscribers: {e}")
            return []

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

    @staticmethod
    def normalize_breaking_news_categories(raw_cat, is_breaking: bool) -> list:
        """Ensures 'Breaking News' tag exists only when is_breaking=True, while preserving domain tags."""
        if isinstance(raw_cat, str):
            try:
                parsed = json.loads(raw_cat)
                cats = parsed if isinstance(parsed, list) else [raw_cat]
            except Exception:
                cats = [c.strip() for c in raw_cat.split(",") if c.strip()]
        elif isinstance(raw_cat, list):
            cats = [str(c).strip() for c in raw_cat if c and str(c).strip()]
        else:
            cats = []

        domains = [c for c in cats if c.lower() != "breaking news"]
        if is_breaking:
            return ["Breaking News"] + domains
        return domains if domains else ["Tech Strategy"]

    @staticmethod
    def is_breaking_news_candidate(
        idx: int,
        raw_pub,
        keep_count: int = 8,
        max_age_hours: int = 24,
        now_utc=None,
    ) -> bool:
        """Returns True only when a post is within the latest `keep_count` and published within `max_age_hours`."""
        if idx >= keep_count:
            return False
        if not max_age_hours or not raw_pub:
            return True
        from datetime import datetime, timezone, timedelta
        ref_now = now_utc or datetime.now(timezone.utc)
        cutoff = ref_now - timedelta(hours=max_age_hours)
        try:
            pub_dt = datetime.fromisoformat(str(raw_pub).replace("Z", "+00:00"))
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            return pub_dt >= cutoff
        except Exception:
            return True

    def sync_breaking_news_tag(self, keep_count: int = 8, max_age_hours: int = 24) -> dict:
        """Keeps 'Breaking News' strictly on the latest `keep_count` posts published within `max_age_hours`."""
        if not self.http_url:
            return {"updated": 0, "added": 0, "removed": 0}

        sql = "SELECT id, category, published_at FROM posts ORDER BY published_at DESC, id DESC LIMIT 750;"
        res = self.execute(sql)
        rows = res.get("results", [{}])[0].get("response", {}).get("result", {}).get("rows", [])

        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)

        statements = []
        added = 0
        removed = 0

        for idx, row in enumerate(rows):
            post_id_obj = row[0] if len(row) > 0 else None
            cat_obj = row[1] if len(row) > 1 else None
            pub_obj = row[2] if len(row) > 2 else None
            post_id = post_id_obj.get("value") if isinstance(post_id_obj, dict) else post_id_obj
            raw_cat = cat_obj.get("value") if isinstance(cat_obj, dict) else cat_obj
            raw_pub = pub_obj.get("value") if isinstance(pub_obj, dict) else pub_obj
            if not post_id:
                continue

            should_break = self.is_breaking_news_candidate(
                idx, raw_pub, keep_count=keep_count, max_age_hours=max_age_hours, now_utc=now_utc
            )
            current_cats = self.normalize_breaking_news_categories(raw_cat, False)
            had_breaking = False
            if raw_cat and "breaking news" in str(raw_cat).lower():
                had_breaking = True

            target_cats = self.normalize_breaking_news_categories(raw_cat, should_break)
            target_json = json.dumps(target_cats)

            # Parse original raw JSON cleanly to avoid needless writes
            try:
                orig_parsed = json.loads(raw_cat) if isinstance(raw_cat, str) and raw_cat.startswith("[") else current_cats
            except Exception:
                orig_parsed = current_cats

            if orig_parsed != target_cats or (should_break != had_breaking):
                statements.append({
                    "sql": "UPDATE posts SET category = ? WHERE id = ?;",
                    "args": [target_json, str(post_id)],
                })
                if should_break and not had_breaking:
                    added += 1
                elif not should_break and had_breaking:
                    removed += 1

        if statements:
            self.execute_batch(statements)
            logging.info(f"[TursoDB] Synced Breaking News tags (latest {keep_count}): +{added} added, -{removed} removed across {len(statements)} row(s).")

        return {"updated": len(statements), "added": added, "removed": removed}


