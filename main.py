import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import os
import sys
import time
import asyncio
import logging
import schedule
import threading
import uvicorn
from dotenv import load_dotenv

from engine.root_agent import RootAgentEngine
from service.data_cleaning.gemini import fast_extract, detect_duplicates
from service.mongodb.client import MongoDBService
from service.mongodb.insert_posts import insert_posts
from service.emails.notify_subscriber import notify_subscribers
from service.cleanup.temp_cleaner import clean_temp_directory
from config.logging_config import setup_logging
from config.model_pool import get_active_model, get_active_key, coordinator

setup_logging()

# Configure timezone
try:
    os.environ['TZ'] = 'Asia/Kathmandu'
    if hasattr(time, 'tzset'):
        time.tzset()
    logging.info("[System] Timezone initialized to Asia/Kathmandu.")
except Exception as e:
    logging.warning(f"[System] Failed to configure timezone: {e}")

load_dotenv()

REQUIRED_ENV = [
    "MONGO_URI",
    "SMTP_SERVER",
    "SMTP_USER",
    "SMTP_PASSWORD"
]

def validate_environment():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    has_api_key = os.getenv("GOOGLE_API_KEYS") or os.getenv("GOOGLE_API_KEY")
    if not has_api_key:
        missing.append("GOOGLE_API_KEY")
    if missing:
        logging.error(f"[Config Error] Missing required environment variables: {', '.join(missing)}")
        raise SystemExit(1)

validate_environment()

async def safe_execute(step_name: str, func, *args, **kwargs):
    """Executes a pipeline step with timing, clean logging, and structured error handling."""
    start_time = time.time()
    try:
        logging.info(f"[{step_name}] Step initiated.")
        result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        elapsed = time.time() - start_time
        logging.info(f"[{step_name}] Step completed successfully in {elapsed:.2f}s.")
        return result
    except Exception as e:
        elapsed = time.time() - start_time
        logging.error(f"[{step_name}] Step failed after {elapsed:.2f}s: {str(e)}")
        return None

async def run_pipeline():
    """
    Executes the autonomous tech intelligence pipeline:
    1. Scouts 24-hr breaking tech news & conducts deep investigative research.
    2. Synthesizes publication-grade markdown articles.
    3. Inserts posts immediately into MongoDB with default image (non-blocking).
    4. Dispatches professional editorial newsletter immediately (text-only).
    5. Deduplicates posts in MongoDB.
    6. Asynchronously synthesizes FLUX.1 visual assets across 4 keys (with 5-min retry backoff) and updates MongoDB.
    """
    active_key = get_active_key()
    masked_key = active_key[:6] + "..." + active_key[-4:] if len(active_key) > 10 else "***"
    
    logging.info("=" * 65)
    logging.info(f"[Pipeline] Cycle started | Model: '{get_active_model()}' | Active Key #{coordinator.key_index + 1} ({masked_key})")
    logging.info("=" * 65)

    try:
        # Step 1: Autonomous research & article generation
        root = RootAgentEngine()
        research_prompt = (
            "Identify the top 2 breakthrough technology developments from the past 24 hours. "
            "Conduct deep technical research on architecture, benchmarks, and developer impact, "
            "and produce publication-ready articles matching the specified JSON schema."
        )
        
        reply = await safe_execute(
            "AgentResearch",
            root.root_agent().agent_response,
            research_prompt
        )
        if not reply:
            logging.warning("[Pipeline] Agent returned no data. Pipeline aborted for this cycle.")
            return False

        # Step 2: Zero-token fast local parsing
        articles = await safe_execute("DataExtraction", fast_extract, reply)
        if not articles or not isinstance(articles, list):
            logging.warning("[Pipeline] Extraction found no valid articles.")
            return False
        logging.info(f"[DataExtraction] Extracted {len(articles)} curated articles with zero token overhead.")

        # Step 3: Immediate MongoDB insertion (asynchronously queues background image generation)
        inserted_docs = await safe_execute("InsertPosts", insert_posts, articles)
        if not inserted_docs:
            logging.warning("[Pipeline] No articles inserted into database.")

        # Step 4: Immediate editorial newsletter dispatch (text-only, professional delivery)
        await safe_execute("NotifySubscribers", notify_subscribers, articles)

        # Step 5: Zero-token fuzzy duplicate detection and cleanup
        mongo_service = MongoDBService()
        existing_posts = await safe_execute("FetchPosts", mongo_service.fetch_all_posts)
        if existing_posts:
            duplicates = await safe_execute("DuplicateDetection", detect_duplicates, existing_posts)
            if duplicates:
                await safe_execute("RemoveDuplicates", mongo_service.remove_duplicate_posts, duplicates)
            else:
                logging.info("[DuplicateDetection] Database clean: 0 duplicate articles detected.")

        logging.info("=" * 65)
        logging.info("[Pipeline] Cycle completed successfully. Articles published and emails dispatched.")
        logging.info("[Pipeline] Background workers are synthesizing FLUX.1 images asynchronously.")
        logging.info("=" * 65)
        return True

    except Exception as e:
        logging.error(f"[Pipeline] Pipeline terminated with error: {str(e)}")
        return False

async def run_daily_cycle():
    """Executes run_pipeline with retry logic in case of upstream network errors."""
    while True:
        success = await run_pipeline()
        if success:
            logging.info("[Scheduler] Pipeline run concluded successfully.")
            break
        else:
            logging.warning("[Scheduler] Pipeline cycle did not produce output. Retrying in 5 minutes...")
            await asyncio.sleep(300)

def start_api_server():
    """Runs the authenticated FastAPI management server."""
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    logging.info(f"[API Server] Management server running on http://{host}:{port}")
    uvicorn.run("api.server:app", host=host, port=port, log_level="warning")

def start_scheduler():
    logging.info("[Scheduler] Autonomous daemon active. Scheduled daily at 05:00 and 17:00 Asia/Kathmandu.")
    schedule.every().day.at("05:00").do(lambda: asyncio.run(run_daily_cycle()))
    schedule.every().day.at("17:00").do(lambda: asyncio.run(run_daily_cycle()))

    # Automated 1-hour temp directory cleanup
    schedule.every(1).hours.do(lambda: clean_temp_directory(max_age_seconds=3600))
    logging.info("[Scheduler] Automated 1-hour temporary folder cleanup job registered.")

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Start authenticated API management server in background thread for live CLI/API interaction
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()

    if "--now" in sys.argv or "--run-now" in sys.argv:
        logging.info("[CLI] Executing immediate on-demand run (--now flag provided)...")
        asyncio.run(run_daily_cycle())
        start_scheduler()
    elif "--api-only" in sys.argv or "--server-only" in sys.argv:
        logging.info("[CLI] Running in dedicated API server mode.")
        while True:
            time.sleep(1)
    else:
        start_scheduler()
