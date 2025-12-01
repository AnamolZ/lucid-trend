import json
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from ..posts_image.posts_image import unsplash_image
from ..data_cleaning.gemini import image_suggestion

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
UNSPLASH_IMAGE = os.getenv("UNSPLASH_IMAGE")

AUTHOR = {
    "name": "Anamol Dhakal",
    "role": "Backend System Developer",
    "avatar": "https://www.anamoldhakal.com.np/blog/assets/avatar-anamol-D1sVnQlG.jpg"
}

DEFAULT_IMAGE = "https://api.imghippo.com/files/dRXB7409pm.png"


def insert_posts(json_path, model=None):
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    documents = []

    for item in data:
        content = item.get("content", "")
        image_url = None

        if model and content:
            keyword = image_suggestion(model, content)
            if keyword:
                image_url = unsplash_image(keyword, UNSPLASH_IMAGE)
                print(image_url)

        if not image_url:
            image_url = DEFAULT_IMAGE

        documents.append({
            **item,
            "image": image_url,
            "thumbnail": image_url,
            "author": AUTHOR
        })

    if not documents:
        print("No documents to insert. Skipping MongoDB insertion.")
        return

    if not MONGO_URI:
        print("MONGO_URI not set. Cannot connect to MongoDB.")
        return

    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    result = collection.insert_many(documents)
    print(f"Inserted {len(result.inserted_ids)} documents into MongoDB.")
    client.close()
