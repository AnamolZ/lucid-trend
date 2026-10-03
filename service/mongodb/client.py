"""Database persistence service for managing articles, deduplication, and subscribers in MongoDB."""

import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class MongoDBService:
    """Provides structured data access and persistence operations on MongoDB collections."""

    def __init__(self, uri: str = None, db_name: str = None, collection_name: str = None):
        self.uri = uri or os.getenv("MONGO_URI")
        self.db_name = db_name or os.getenv("DATABASE_NAME", "portfolio_db")
        self.collection_name = collection_name or os.getenv("COLLECTION_NAME", "posts")

    def _get_client(self) -> MongoClient:
        if not self.uri:
            raise ValueError("MongoDB URI is not configured.")
        return MongoClient(self.uri)

    def insert_documents(self, documents: list) -> list:
        """Persists newly synthesized article documents into the collection."""
        if not documents:
            return []
        with self._get_client() as client:
            db = client[self.db_name]
            col = db[self.collection_name]
            res = col.insert_many(documents)
            inserted_count = len(res.inserted_ids)
            logging.info(f"[MongoDB] Inserted {inserted_count} articles into '{self.collection_name}'.")
            return res.inserted_ids

    def fetch_all_posts(self) -> list:
        """Retrieves lightweight article metadata for local duplicate detection."""
        with self._get_client() as client:
            db = client[self.db_name]
            col = db[self.collection_name]
            posts = list(col.find({}, {"_id": 0, "id": 1, "title": 1, "description": 1}))
            logging.info(f"[MongoDB] Fetched {len(posts)} existing posts.")
            return posts

    def remove_duplicate_posts(self, duplicate_ids: list) -> int:
        """Deletes database records matching the specified duplicate article identifiers."""
        if not duplicate_ids:
            return 0
        with self._get_client() as client:
            db = client[self.db_name]
            col = db[self.collection_name]
            total_deleted = 0
            for dup_id in duplicate_ids:
                res = col.delete_many({"id": dup_id})
                total_deleted += res.deleted_count
                logging.info(f"[MongoDB] Deleted duplicate post: {dup_id}")
            return total_deleted

    def get_verified_subscribers(self, sub_collection: str = "notification_address") -> list:
        """Queries and returns the list of verified newsletter subscriber email addresses."""
        with self._get_client() as client:
            db = client[self.db_name]
            col = db[sub_collection]
            cursor = col.find({"isVerified": True}, {"_id": 0, "email": 1})
            emails = [doc["email"] for doc in cursor if doc.get("email")]
            logging.info(f"[MongoDB] Found {len(emails)} verified subscribers.")
            return emails

    def update_post_image(self, post_id: str, image_url: str) -> int:
        """Updates the image and thumbnail URLs in-place for a specific article document."""
        if not post_id or not image_url:
            return 0
        with self._get_client() as client:
            db = client[self.db_name]
            col = db[self.collection_name]
            res = col.update_one(
                {"id": post_id},
                {"$set": {"image": image_url, "thumbnail": image_url}}
            )
            logging.info(
                f"[MongoDB] Post '{post_id}' image updated: matched={res.matched_count}, modified={res.modified_count}"
            )
            return res.modified_count
