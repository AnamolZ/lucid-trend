"""Neon PostgreSQL persistence service for managing articles and deduplication."""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

class NeonDBService:
    """Provides structured data access and persistence operations on Neon PostgreSQL."""

    def __init__(self, dsn: str = None):
        self.dsn = dsn or os.getenv("NEON_DB")

    def _get_connection(self):
        if not self.dsn:
            raise ValueError("NEON_DB connection string is not configured.")
        return psycopg2.connect(self.dsn)

    def delete_older_than_days(self, days: int = 7) -> int:
        """Purges articles older than `days` based on created_at timestamp."""
        if not self.dsn:
            logging.warning("[NeonDB] NEON_DB not configured. Skipping purge.")
            return 0

        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
        logging.info(f"[NeonDB] Scanning 'posts' table for records older than {days} days (cutoff: {cutoff_dt.isoformat()})...")
        deleted_count = 0
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM posts WHERE created_at < %s;", (cutoff_dt,))
                    deleted_count = cur.rowcount
                conn.commit()
            if deleted_count > 0:
                logging.info(
                    f"[NeonDB] Purged {deleted_count} posts older than {days} days (cutoff: {cutoff_dt.isoformat()})."
                )
            else:
                logging.info(
                    f"[NeonDB] No posts older than {days} days found in 'posts'."
                )
        except Exception as e:
            logging.error(f"[NeonDB] Error purging posts older than {days} days: {e}")
            raise
        return deleted_count

    def insert_documents(self, documents: list, purge_older_than_days: int = 7) -> list:
        """Persists article documents into Neon 'posts' table, purging posts older than threshold first."""
        if not self.dsn:
            logging.warning("[NeonDB] NEON_DB not configured. Skipping insert.")
            return []

        if purge_older_than_days is not None and purge_older_than_days > 0:
            try:
                self.delete_older_than_days(days=purge_older_than_days)
            except Exception as e:
                logging.error(f"[NeonDB] Failed to delete old posts before insertion: {e}")

        if not documents:
            return []

        inserted_ids = []
        upsert_query = """
            INSERT INTO posts (id, title, slug, description, content, image, thumbnail, category, author, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                slug = EXCLUDED.slug,
                description = EXCLUDED.description,
                content = EXCLUDED.content,
                image = EXCLUDED.image,
                thumbnail = EXCLUDED.thumbnail,
                category = EXCLUDED.category,
                author = EXCLUDED.author
            RETURNING id;
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    for doc in documents:
                        doc_id = doc.get("id")
                        if not doc_id:
                            continue

                        title = doc.get("title")
                        slug = doc.get("slug") or doc_id
                        description = doc.get("description")
                        content = doc.get("content")
                        image = doc.get("image")
                        thumbnail = doc.get("thumbnail")

                        category = doc.get("category")
                        if category is not None and not isinstance(category, str):
                            category_json = json.dumps(category)
                        elif isinstance(category, str):
                            category_json = category
                        else:
                            category_json = json.dumps([])

                        author = doc.get("author")
                        if author is not None and not isinstance(author, str):
                            author_json = json.dumps(author)
                        elif isinstance(author, str):
                            author_json = author
                        else:
                            author_json = json.dumps({})

                        # Handle created_at
                        doc_date = doc.get("created_at") or doc.get("date") or doc.get("published_at")
                        if isinstance(doc_date, str):
                            try:
                                created_at = datetime.fromisoformat(doc_date)
                            except Exception:
                                created_at = datetime.now(timezone.utc)
                        elif isinstance(doc_date, datetime):
                            created_at = doc_date
                        else:
                            created_at = datetime.now(timezone.utc)

                        cur.execute(
                            upsert_query,
                            (doc_id, title, slug, description, content, image, thumbnail, category_json, author_json, created_at)
                        )
                        res = cur.fetchone()
                        if res:
                            inserted_ids.append(res[0])
                conn.commit()

            logging.info(
                f"[NeonDB] Processed {len(documents)} articles (upserted: {len(inserted_ids)}) into 'posts'."
            )
        except Exception as e:
            logging.error(f"[NeonDB] Error inserting documents: {e}")
            raise

        return inserted_ids

    def update_post_image(self, post_id: str, image_url: str) -> int:
        """Updates the image and thumbnail URLs in-place for a specific article in Neon."""
        if not self.dsn or not post_id or not image_url:
            return 0
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE posts SET image = %s, thumbnail = %s WHERE id = %s;",
                        (image_url, image_url, post_id)
                    )
                    modified_count = cur.rowcount
                conn.commit()
            logging.info(
                f"[NeonDB] Post '{post_id}' image updated: modified={modified_count}"
            )
            return modified_count
        except Exception as e:
            logging.error(f"[NeonDB] Failed to update image for post '{post_id}': {e}")
            return 0
