
import json
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from service.image_helper.get_image import unsplash_image, huggingface_image
from service.data_cleaning.gemini import image_suggestion, image_generation_prompt

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
UNSPLASH_IMAGE = os.getenv("UNSPLASH_IMAGE")
HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKEN")

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
                try:
                    generation_prompt = image_generation_prompt(model, content)
                    if generation_prompt:
                        image_url = huggingface_image(HUGGING_FACE_TOKEN, generation_prompt)
                except Exception:
                    image_url = None

                if not image_url:
                    try:
                        image_url = unsplash_image(keyword, UNSPLASH_IMAGE)
                    except Exception:
                        image_url = None

        if not image_url:
            image_url = DEFAULT_IMAGE

        documents.append({
            **item,
            "image": image_url,
            "thumbnail": image_url,
            "author": AUTHOR
        })

    if not documents or not MONGO_URI:
        return

    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]
    result = collection.insert_many(documents)
    print(f"Inserted {len(result.inserted_ids)} documents into MongoDB.")
    client.close()