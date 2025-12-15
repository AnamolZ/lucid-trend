
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import os
import asyncio
import json
import schedule
import time
import logging
from dotenv import load_dotenv
from google.generativeai import GenerativeModel, configure

from engine.news_engine import NewsEngine
from engine.dsearch_engine import DeepSearchEngine
from engine.root_agent import RootAgentEngine

from service.data_cleaning.gemini import extract, detect_duplicates
from service.mongodb.insert_posts import insert_posts
from service.mongodb.fetch_posts import fetch_posts
from service.mongodb.remove_posts import remove_duplicates
from service.emails.notify_subscriber import notify_subscribers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

try:
    os.environ['TZ'] = 'Asia/Kathmandu'
    if hasattr(time, 'tzset'):
        time.tzset()
    logging.info("Timezone set to Asia/Kathmandu")
except Exception as e:
    logging.warning(f"Failed to set timezone: {e}")

load_dotenv()

REQUIRED_ENV = [
    "MONGO_URI",
    "DATABASE_NAME",
    "COLLECTION_NAME",
    "GOOGLE_API_KEY",
    "SMTP_SERVER",
    "SMTP_USER",
    "SMTP_PASSWORD"
]

def validate_env():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        logging.error(f"Missing required environment variables: {', '.join(missing)}")
        raise SystemExit(1)

validate_env()

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

async def safe_execute(name, func, *args, **kwargs):
    try:
        logging.info(f"{name} started")
        result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        logging.info(f"{name} completed")
        return result
    except Exception as e:
        logging.error(f"{name} failed: {str(e)}")
        return None

async def run_job():
    logging.info("Job started")
    try:
        configure(api_key=GOOGLE_API_KEY)
        model = GenerativeModel("gemini-2.5-flash")

        await safe_execute("NewsEngine", lambda: NewsEngine().news_agent())
        await safe_execute("DeepSearchEngine", lambda: DeepSearchEngine().dsearch_agent())

        root = RootAgentEngine()
        reply = await safe_execute(
            "RootAgentEngine",
            root.root_agent().agent_response,
            "Fetch the most recent important tech news from the past 24 hours, perform a deep-dive investigation into the most recent tech news for a provided headlines"
        )
        if not reply:
            logging.warning("Root agent returned no data")
            return False

        extracted = await safe_execute("Extraction", extract, reply, model)
        if not extracted:
            logging.warning("Extraction returned no data")
            return False

        with open("service/blog/extracted_data.json", "w", encoding="utf-8") as f:
            json.dump(extracted, f, ensure_ascii=False, indent=2)

        await safe_execute("InsertPosts", insert_posts, "service/blog/extracted_data.json", model)

        posts = await safe_execute("FetchPosts", fetch_posts, MONGO_URI, DATABASE_NAME, COLLECTION_NAME)
        if not posts:
            logging.info("No posts found to process")
            return True

        duplicates = await safe_execute("DuplicateDetection", detect_duplicates, posts, model)
        if duplicates is None:
            logging.warning("Duplicate detection failed")
            return False

        await safe_execute("RemoveDuplicates", remove_duplicates, duplicates, MONGO_URI, DATABASE_NAME, COLLECTION_NAME)

        cleaned = [p for p in posts if p["id"] not in duplicates]
        with open("service/blog/clean_posts.json", "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=4)

        await safe_execute("NotifySubscribers", notify_subscribers, model, MONGO_URI, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD)
        
        for temp_file in ["service/blog/extracted_data.json", "service/blog/clean_posts.json"]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                logging.info(f"Removed temporary file: {temp_file}")

        logging.info("Job finished successfully")
        return True

    except Exception as e:
        logging.error(f"Job failed unexpectedly: {str(e)}")
        return False

async def run_daily_cycle():
    logging.info("Starting daily cycle...")
    while True:
        success = await run_job()
        if success:
            logging.info("Daily job executed successfully.")
            break
        else:
            logging.warning("Daily job failed or returned no data. Retrying in 10 minutes...")
            await asyncio.sleep(600)

def start_scheduler():
    logging.info("Scheduler started. Job scheduled for 5:00 daily.")
    schedule.every().day.at("4:57").do(lambda: asyncio.run(run_daily_cycle()))
    # schedule.every().day.at("21:00").do(lambda: asyncio.run(run_daily_cycle()))

    # logging.info("Scheduler started. Job scheduled every 1 minute.")
    # schedule.every(1).minutes.do(lambda: asyncio.run(run_daily_cycle()))
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    start_scheduler()
