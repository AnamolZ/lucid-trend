"""Database persistence service for managing articles, deduplication, and subscribers in MongoDB."""

import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_shared_mongo_client = None

def get_shared_client(uri: str) -> MongoClient:
    """Maintains a persistent, thread-safe MongoClient connection pool."""
    global _shared_mongo_client
    if _shared_mongo_client is None:
        _shared_mongo_client = MongoClient(
            uri,
            maxPoolSize=50,
            minPoolSize=5,
            serverSelectionTimeoutMS=5000
        )
    return _shared_mongo_client

class MongoDBService:
    """Provides structured data access and persistence operations on MongoDB collections."""

    def __init__(self, uri: str = None, db_name: str = None, collection_name: str = None):
        self.uri = uri or os.getenv("MONGO_URI")
        self.db_name = db_name or os.getenv("DATABASE_NAME", "portfolio_db")
        self.collection_name = collection_name or os.getenv("COLLECTION_NAME", "posts")

    def _get_client(self) -> MongoClient:
        if not self.uri:
            raise ValueError("MongoDB URI is not configured.")
        return get_shared_client(self.uri)

    def insert_documents(self, documents: list) -> list:
        """Persists article documents into collection, using upsert to prevent accidental duplicates."""
        if not documents:
            return []
        client = self._get_client()
        db = client[self.db_name]
        col = db[self.collection_name]

        inserted_ids = []
        for doc in documents:
            doc_id = doc.get("id")
            if doc_id:
                res = col.update_one(
                    {"id": doc_id},
                    {"$setOnInsert": doc},
                    upsert=True
                )
                if res.upserted_id:
                    inserted_ids.append(res.upserted_id)
            else:
                res = col.insert_one(doc)
                inserted_ids.append(res.inserted_id)

        logging.info(
            f"[MongoDB] Processed {len(documents)} articles (newly inserted: {len(inserted_ids)}) into '{self.collection_name}'."
        )
        return inserted_ids

    def fetch_all_posts(self) -> list:
        """Retrieves lightweight article metadata including _id for accurate duplicate detection."""
        client = self._get_client()
        db = client[self.db_name]
        col = db[self.collection_name]
        posts = list(col.find({}, {"_id": 1, "id": 1, "title": 1, "description": 1}))
        logging.info(f"[MongoDB] Fetched {len(posts)} existing posts.")
        return posts

    def remove_duplicate_posts(self, duplicate_ids: list) -> int:
        """Purges duplicate records while safely preserving the original article document."""
        if not duplicate_ids:
            return 0

        client = self._get_client()
        db = client[self.db_name]
        col = db[self.collection_name]

        from bson import ObjectId
        mongo_ids = []
        string_ids = []

        for d in duplicate_ids:
            if isinstance(d, ObjectId):
                mongo_ids.append(d)
            elif isinstance(d, str) and ObjectId.is_valid(d):
                mongo_ids.append(ObjectId(d))
            else:
                string_ids.append(d)

        total_deleted = 0
        if mongo_ids:
            res = col.delete_many({"_id": {"$in": mongo_ids}})
            total_deleted += res.deleted_count

        if string_ids:
            # If string ids provided, delete only excess copies beyond the first instance
            for s_id in string_ids:
                docs = list(col.find({"id": s_id}, {"_id": 1}))
                if len(docs) > 1:
                    excess_ids = [doc["_id"] for doc in docs[1:]]
                    res = col.delete_many({"_id": {"$in": excess_ids}})
                    total_deleted += res.deleted_count

        logging.info(f"[MongoDB] Purged {total_deleted} duplicate documents (originals preserved).")
        return total_deleted

    def get_verified_subscribers(self, sub_collection: str = "notification_address") -> list:
        """Queries and returns the list of verified newsletter subscriber email addresses."""
        client = self._get_client()
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
        client = self._get_client()
        db = client[self.db_name]
        col = db[self.collection_name]
        from bson import ObjectId
        query = {"id": post_id}
        if isinstance(post_id, ObjectId):
            query = {"_id": post_id}
        elif isinstance(post_id, str) and ObjectId.is_valid(post_id):
            query = {"$or": [{"id": post_id}, {"_id": ObjectId(post_id)}]}

        res = col.update_one(
            query,
            {"$set": {"image": image_url, "thumbnail": image_url}}
        )
        logging.info(
            f"[MongoDB] Post '{post_id}' image updated: matched={res.matched_count}, modified={res.modified_count}"
        )
        return res.modified_count
