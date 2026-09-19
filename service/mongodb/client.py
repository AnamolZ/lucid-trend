import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

class MongoDBService:
    """
    Unified MongoDB management service for LucidTrend.
    Handles blog posts, deduplication, and verified subscriber retrieval.
    """
    def __init__(self, uri=None, db_name=None, collection_name=None):
        self.uri = uri or os.getenv("MONGO_URI")
        self.db_name = db_name or os.getenv("DATABASE_NAME", "portfolio_db")
        self.collection_name = collection_name or os.getenv("COLLECTION_NAME", "posts")

    def _get_client(self):
        if not self.uri:
            raise ValueError("MongoDB URI is not configured.")
        return MongoClient(self.uri)

    def insert_documents(self, documents):
        """Inserts processed article documents into MongoDB."""
        if not documents:
            return []
        with self._get_client() as client:
            db = client[self.db_name]
            col = db[self.collection_name]
            res = col.insert_many(documents)
            inserted_count = len(res.inserted_ids)
            logging.info(f"[MongoDB] Inserted {inserted_count} articles into '{self.collection_name}'.")
            return res.inserted_ids

    def fetch_all_posts(self):
        """Fetches lightweight post identifiers for deduplication."""
        with self._get_client() as client:
            db = client[self.db_name]
            col = db[self.collection_name]
            posts = list(col.find({}, {"_id": 0, "id": 1, "title": 1, "description": 1}))
            logging.info(f"[MongoDB] Fetched {len(posts)} existing posts.")
            return posts

    def remove_duplicate_posts(self, duplicate_ids):
        """Deletes posts matching duplicate IDs."""
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

    def get_verified_subscribers(self, sub_collection="notification_address"):
        """Retrieves list of verified newsletter subscriber email addresses."""
        with self._get_client() as client:
            db = client[self.db_name]
            col = db[sub_collection]
            cursor = col.find({"isVerified": True}, {"_id": 0, "email": 1})
            emails = [doc["email"] for doc in cursor if doc.get("email")]
            logging.info(f"[MongoDB] Found {len(emails)} verified subscribers.")
            return emails
