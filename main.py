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
from service.tursodb.client import TursoDBService
from service.posts.insert_posts import insert_posts
from service.export.static_baker import bake_static_payloads
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
    "TURSO_DATABASE_URL",
    "TURSO_AUTH_TOKEN",
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

async def run_pipeline(target_category: str = None) -> bool:
    """Executes targeted autonomous intelligence scouting, article extraction, database publication, and email dispatch."""
    from engine.slot_coordinator import resolve_active_slot, fetch_category_exclusions
    from service.telemetry.quota_tracker import telemetry_tracker

    slot_info = resolve_active_slot(target_category)
    cat_key = slot_info["category_key"]
    pillar_title = slot_info["pillar_info"]["pillar"]
    slot_label = slot_info["label"]

    active_key = get_active_key()
    active_model = get_active_model()
    masked_key = active_key[:6] + "..." + active_key[-4:] if len(active_key) > 10 else "***"

    logging.info("=" * 78)
    logging.info(f"[Pipeline] Micro-Dispatch Cycle Started | Slot #{slot_info['slot']}: {slot_label}")
    logging.info(f"[Pipeline] Category: {cat_key} ({pillar_title}) | Model: '{active_model}'")
    logging.info("=" * 78)

    try:
        # 1. Fetch past 15 titles strictly from this category for upstream exclusion
        exclusions = fetch_category_exclusions(cat_key, limit=15)

        root = RootAgentEngine()
        research_prompt = (
            f"Identify the single most significant breaking development in '{pillar_title}' from the past 24 hours. "
            f"Conduct rigorous technical / financial / geopolitical analysis and synthesize exactly ONE publication-ready article matching the specified JSON schema."
        )

        reply = await safe_execute(
            "AgentResearch",
            root.root_agent().agent_response,
            research_prompt,
            category_key=cat_key,
            exclusions=exclusions
        )
        if not reply:
            logging.warning("[Pipeline] Agent returned no data. Pipeline aborted for this cycle.")
            return False

        articles = await safe_execute("DataExtraction", fast_extract, reply)
        if not articles or not isinstance(articles, list):
            logging.warning("[Pipeline] Extraction found no valid articles.")
            return False
        logging.info(f"[DataExtraction] Extracted {len(articles)} curated article(s) with zero token overhead.")

        inserted_docs = await safe_execute("InsertPosts", insert_posts, articles)
        if not inserted_docs:
            logging.warning("[Pipeline] No articles inserted into database.")

        await safe_execute("NotifySubscribers", notify_subscribers, articles)

        turso_service = TursoDBService()
        existing_posts = await safe_execute("FetchPosts", turso_service.fetch_all_posts)
        if existing_posts:
            duplicates = await safe_execute("DuplicateDetection", detect_duplicates, existing_posts)
            if duplicates:
                await safe_execute("RemoveTursoDuplicates", turso_service.remove_duplicate_posts, duplicates)
                await safe_execute("RebakeStaticPayloads", bake_static_payloads)
            else:
                logging.info("[DuplicateDetection] Database clean: 0 duplicate articles detected.")

        logging.info("=" * 78)
        logging.info("[Pipeline] Targeted micro-dispatch cycle completed successfully.")
        # Log enterprise quota telemetry banner
        telemetry_banner = telemetry_tracker.get_telemetry_banner(
            coordinator.raw_keys,
            coordinator.key_index,
            active_model
        )
        logging.info("\n" + telemetry_banner)
        logging.info("=" * 78)
        return True

    except Exception as e:
        logging.error(f"[Pipeline] Pipeline terminated with error: {str(e)}")
        return False

async def run_daily_cycle(target_category: str = None):
    """Runs pipeline cycles with automated retry backoff on upstream network failures."""
    while True:
        success = await run_pipeline(target_category=target_category)
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

    # Check for manual category override (e.g. --category=Finance or --category=Geopolitics)
    target_cat = None
    for arg in sys.argv:
        if arg.startswith("--category="):
            target_cat = arg.split("=", 1)[1].strip()
        elif arg == "--category" and sys.argv.index(arg) + 1 < len(sys.argv):
            target_cat = sys.argv[sys.argv.index(arg) + 1].strip()

    if "--once" in sys.argv:
        logging.info(f"[CLI] Executing single autonomous publish run (--once flag provided, category={target_cat or 'AUTO'})...")
        asyncio.run(run_daily_cycle(target_category=target_cat))
        logging.info("[CLI] Autonomous single run completed. Exiting.")
        sys.exit(0)
    elif "--now" in sys.argv or "--run-now" in sys.argv:
        logging.info(f"[CLI] Executing immediate on-demand run (--now flag provided, category={target_cat or 'AUTO'})...")
        asyncio.run(run_daily_cycle(target_category=target_cat))
        start_scheduler()
    elif "--api-only" in sys.argv or "--server-only" in sys.argv:
        logging.info("[CLI] Running in dedicated API server mode.")
        while True:
            time.sleep(1)
    else:
        start_scheduler()
