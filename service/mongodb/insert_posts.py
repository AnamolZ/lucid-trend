
import json
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from celery import group
from service.tasks.tasks import generate_image_task

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

def insert_posts(json_path, model=None):
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not data:
        return

    job = group([generate_image_task.s(item) for item in data])
    result = job.apply_async()
    documents = result.join()

    if not documents or not MONGO_URI:
        return

    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]
    insert_result = collection.insert_many(documents)
    print(f"Inserted {len(insert_result.inserted_ids)} documents into MongoDB.")
    client.close()