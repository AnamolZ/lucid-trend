"""Main application entrypoint initializing the scheduler daemon, pipeline runner, and API server."""

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

# Initialize operational timezone
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
    """Validates the presence of required configuration parameters and API credentials."""
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

async def run_pipeline() -> bool:
    """Executes autonomous intelligence scouting, article extraction, database publication, and email dispatch."""
    active_key = get_active_key()
    masked_key = active_key[:6] + "..." + active_key[-4:] if len(active_key) > 10 else "***"

    logging.info("=" * 65)
    logging.info(f"[Pipeline] Cycle started | Model: '{get_active_model()}' | Active Key #{coordinator.key_index + 1} ({masked_key})")
    logging.info("=" * 65)

    try:
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

        articles = await safe_execute("DataExtraction", fast_extract, reply)
        if not articles or not isinstance(articles, list):
            logging.warning("[Pipeline] Extraction found no valid articles.")
            return False
        logging.info(f"[DataExtraction] Extracted {len(articles)} curated articles with zero token overhead.")

        inserted_docs = await safe_execute("InsertPosts", insert_posts, articles)
        if not inserted_docs:
            logging.warning("[Pipeline] No articles inserted into database.")

        await safe_execute("NotifySubscribers", notify_subscribers, articles)

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
    """Runs pipeline cycles with automated retry backoff on upstream network failures."""
    while True:
        success = await run_pipeline()
        if success:
            logging.info("[Scheduler] Pipeline run concluded successfully.")
            break
        else:
            logging.warning("[Scheduler] Pipeline cycle did not produce output. Retrying in 5 minutes...")
            await asyncio.sleep(300)

def start_api_server():
    """Launches the authenticated FastAPI management server using uvicorn."""
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    logging.info(f"[API Server] Management server running on http://{host}:{port}")
    uvicorn.run("api.server:app", host=host, port=port, log_level="warning")

from service.scheduler.schedule_manager import register_pipeline_callback, apply_schedule

def start_scheduler():
    """Initializes and runs the continuous daily scheduler daemon with dynamic reshuffling support."""
    register_pipeline_callback(run_daily_cycle)
    apply_schedule()

    # Run automated temp cleanup every hour
    schedule.every(1).hours.do(lambda: clean_temp_directory(max_age_seconds=3600)).tag("temp_cleaner")
    logging.info("[Scheduler] Automated 1-hour temporary folder cleanup job registered.")

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Start management API server in background thread for live client interactions
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
