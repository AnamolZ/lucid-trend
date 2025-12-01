
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import os
import asyncio
from engine.news_engine import NewsEngine
from engine.dsearch_engine import DeepSearchEngine
from engine.root_agent import RootAgentEngine
from dotenv import load_dotenv
from google.generativeai import GenerativeModel, configure
from service.data_cleaning.gemini import extract
import json
from service.mongodb.insert_posts import insert_posts
from service.mongodb.fetch_posts import fetch_posts
from service.mongodb.remove_posts import remove_duplicates
from service.data_cleaning.gemini import detect_duplicates
from service.emails.notify_subscriber import notify_subscribers

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

async def run_main():
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY not found in environment.")
        return
    
    api_key = os.getenv("GOOGLE_API_KEY")
    configure(api_key=api_key)
    model = GenerativeModel("gemini-2.5-flash")

    news_fetch = NewsEngine()
    news_fetch.news_agent()

    deep_engine = DeepSearchEngine()
    deep_engine.dsearch_agent()

    root_agent = RootAgentEngine()
    reply = await root_agent.root_agent().agent_response(
        "Fetch the most recent important tech news from the past 24 hours, perform a deep-dive investigation into the most recent tech news for a provided headlines"
    )

    extracted = extract(reply, model)
    with open("extracted_data.json", "w", encoding="utf-8") as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2)

    insert_posts("extracted_data.json", model)

    posts = fetch_posts(MONGO_URI, DATABASE_NAME, COLLECTION_NAME)

    if not posts:
        print("No posts found in database.")
        return
    
    duplicates = detect_duplicates(posts, model)
    remove_duplicates(duplicates, MONGO_URI, DATABASE_NAME, COLLECTION_NAME)
    
    clean_posts = [p for p in posts if p["id"] not in duplicates]
    with open("clean_posts.json", "w", encoding="utf-8") as f:
        json.dump(clean_posts, f, ensure_ascii=False, indent=4)

    # notify_subscribers(model, MONGO_URI, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD)

def main():
    asyncio.run(run_main())

if __name__ == "__main__":
    main()