"""FastAPI management and execution server with authenticated REST endpoints."""

import os
import re
import time
import uuid
import secrets
import base64
import asyncio
import logging
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Security, status, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from engine.root_agent import RootAgentEngine
from service.data_cleaning.gemini import fast_extract, detect_duplicates
from service.image_helper.get_image import huggingface_image, hf_coordinator
from service.mongodb.client import MongoDBService
from service.mongodb.insert_posts import insert_posts
from service.emails.notify_subscriber import notify_subscribers
from service.cleanup.temp_cleaner import ensure_temp_dir, clean_temp_directory, TEMP_DIR
from service.scheduler.schedule_manager import get_active_schedule, reshuffle_schedule
from config.model_pool import get_active_model, get_active_key, coordinator
from config.logging_config import setup_logging

load_dotenv()
setup_logging()

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "lt_sec_default_key_2026")
MASTER_PASSWORD = os.getenv("MASTER_PASSWORD", "lucidtrend1379")

def update_env_api_key(new_key: str):
    """Safely updates or inserts API_SECRET_KEY in the .env file on disk."""
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            if re.search(r"^API_SECRET_KEY=.*", content, flags=re.MULTILINE):
                content = re.sub(r"^API_SECRET_KEY=.*", f"API_SECRET_KEY={new_key}", content, flags=re.MULTILINE)
            else:
                content += f"\nAPI_SECRET_KEY={new_key}\n"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logging.error(f"[Security] Failed to write updated API key to .env: {e}")

# Support both X-API-Key header and Bearer token authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

def verify_api_key(
    request: Request,
    header_key: Optional[str] = Security(api_key_header),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> str:
    """Validates incoming requests against the configured secret API key and logs security alerts."""
    token = header_key or (bearer_creds.credentials if bearer_creds else None)
    client_ip = request.client.host if request.client else "unknown"
    if not token or token != API_SECRET_KEY:
        masked = (token[:4] + "..." + token[-2:]) if token and len(token) > 6 else (token or "None")
        logging.warning(
            f"[Security Alert] Unauthorized access attempt from {client_ip} rejected! Invalid or missing API key (received: '{masked}')."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid API key. Provide via 'X-API-Key' or 'Authorization: Bearer <key>'."
        )
    logging.info(f"[Security] Client authenticated successfully from {client_ip}.")
    return token

app = FastAPI(
    title="LucidTrend Intelligence API",
    description="Autonomous Tech Intelligence Engine - Management & Execution API",
    version="1.0.0"
)

# Expose temporary directory as static route for file downloads
ensure_temp_dir()
app.mount("/temp", StaticFiles(directory=TEMP_DIR), name="temp")

class PipelineRequest(BaseModel):
    """Execution parameters for modular pipeline runs."""
    with_db: bool = Field(default=True, description="Whether to write articles to MongoDB")
    with_email: bool = Field(default=True, description="Whether to dispatch newsletter emails")
    with_image: bool = Field(default=True, description="Whether to trigger async image generation")
    research_prompt: Optional[str] = Field(
        default=None,
        description="Custom research prompt for Gemini intelligence scout"
    )

class ImageGenerationRequest(BaseModel):
    """Payload for isolated image generation requests."""
    prompt: Optional[str] = Field(default=None, description="Image generation prompt for FLUX.1")
    title: Optional[str] = Field(default=None, description="Article title to construct prompt from if prompt omitted")

class EmailTestRequest(BaseModel):
    """Payload for subscriber email test dispatches."""
    to_email: Optional[str] = Field(default=None, description="Optional recipient email address")

class PushTestRequest(BaseModel):
    """Payload for mobile push test broadcasts."""
    title: Optional[str] = Field(default="NewsPluk | Push Notification Test", description="Notification title")
    body: Optional[str] = Field(default="Firebase background push delivered successfully!", description="Notification body")
    post_id: Optional[str] = Field(default="test-push", description="Post ID for deep-linking")
    topic: Optional[str] = Field(default="all_news", description="Firebase topic")

class RotateKeyRequest(BaseModel):
    """Payload for rotating the system API key via master password."""
    master_password: str = Field(..., description="Master administration password")

@app.get("/api/v1/status", dependencies=[Depends(verify_api_key)])
async def get_system_status():
    """Returns real-time health metrics, active models, key statuses, and temp dir stats."""
    active_key = get_active_key()
    masked_key = active_key[:6] + "..." + active_key[-4:] if len(active_key) > 10 else "***"
    hf_tokens = hf_coordinator.get_tokens()

    temp_files = os.listdir(TEMP_DIR) if os.path.exists(TEMP_DIR) else []
    scheduled_runs = get_active_schedule()

    return {
        "status": "online",
        "service": "LucidTrend Autonomous System",
        "active_gemini_model": get_active_model(),
        "active_gemini_key": masked_key,
        "huggingface_keys_count": len(hf_tokens),
        "huggingface_active_key_index": hf_coordinator.key_index + 1,
        "temp_files_count": len(temp_files),
        "scheduled_daily_runs": scheduled_runs,
        "schedule_interval": "12 hours (2 runs per day)",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@app.post("/api/v1/image/generate", dependencies=[Depends(verify_api_key)])
async def generate_image_endpoint(req: ImageGenerationRequest):
    """Generates an image via FLUX.1 without blocking the asyncio loop, returning download URL and base64."""
    prompt = req.prompt
    if not prompt and req.title:
        prompt = f"Cinematic digital illustration of {req.title}, futuristic, clean 16:9 composition"

    if not prompt:
        raise HTTPException(status_code=400, detail="Either 'prompt' or 'title' must be provided.")

    logging.info("=" * 65)
    logging.info(f"[API ImageGeneration] Generating image for prompt:")
    logging.info(f"  -> \"{prompt}\"")
    logging.info("=" * 65)

    data_uri = await asyncio.to_thread(
        huggingface_image,
        prompt=prompt,
        title=req.title,
        max_rounds=1,
        wait_seconds=0
    )

    if not data_uri:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate image across all Hugging Face keys after retries."
        )

    filename = f"flux_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
    temp_file_path = os.path.join(TEMP_DIR, filename)

    base64_data = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
    image_bytes = base64.b64decode(base64_data)

    await asyncio.to_thread(
        lambda: open(temp_file_path, "wb").write(image_bytes)
    )

    logging.info(f"[API ImageGeneration] Saved temporary image to '{temp_file_path}' ({len(image_bytes):,} bytes).")

    return {
        "success": True,
        "prompt_used": prompt,
        "filename": filename,
        "temp_file_path": temp_file_path,
        "download_url": f"/temp/{filename}",
        "image_data_uri": data_uri,
        "size_bytes": len(image_bytes)
    }

@app.post("/api/v1/pipeline/run", dependencies=[Depends(verify_api_key)])
async def run_pipeline_endpoint(req: PipelineRequest):
    """Triggers intelligence scouting and publishing with modular module toggles and non-blocking I/O."""
    logging.info("=" * 65)
    logging.info(
        f"[API Pipeline] Initiating run | DB: {req.with_db} | Email: {req.with_email} | Images: {req.with_image}"
    )
    logging.info("=" * 65)

    prompt = req.research_prompt or (
        "Identify the top 2 breakthrough technology developments from the past 24 hours. "
        "Conduct deep technical research on architecture, benchmarks, and developer impact, "
        "and produce publication-ready articles matching the specified JSON schema."
    )

    root = RootAgentEngine()
    reply = await root.root_agent().agent_response(prompt)
    if not reply:
        raise HTTPException(status_code=500, detail="Intelligence agent returned no data.")

    articles = fast_extract(reply)
    if not articles or not isinstance(articles, list):
        raise HTTPException(status_code=500, detail="Failed to parse structured articles from agent output.")

    logging.info(f"[API Pipeline] Synthesized {len(articles)} articles.")

    for idx, item in enumerate(articles, 1):
        logging.info(f"[Article #{idx}] Title: {item.get('title')}")
        logging.info(f"[Article #{idx}] FLUX.1 Prompt: {item.get('image_prompt')}")

    inserted_docs = []
    if req.with_db:
        inserted_docs = await asyncio.to_thread(insert_posts, articles, with_image=req.with_image)
        logging.info(f"[API Pipeline] Inserted {len(inserted_docs)} posts into MongoDB.")

    email_dispatched = False
    if req.with_email:
        email_dispatched = await asyncio.to_thread(notify_subscribers, articles)
        logging.info(f"[API Pipeline] Newsletter dispatched: {email_dispatched}")

    # Reshuffle schedule on forced run to set new random daily times with exact 12-hour gap
    time1, time2 = reshuffle_schedule()
    logging.info(f"[API Pipeline] Dynamic schedule reshuffled to: {time1} and {time2} (12h gap).")

    return {
        "success": True,
        "articles_count": len(articles),
        "articles": [
            {
                "id": a.get("id"),
                "title": a.get("title"),
                "category": a.get("category"),
                "description": a.get("description"),
                "image_prompt": a.get("image_prompt")
            }
            for a in articles
        ],
        "database_inserted": req.with_db,
        "email_dispatched": email_dispatched,
        "images_queued": req.with_image,
        "reshuffled_schedule": [time1, time2]
    }

@app.post("/api/v1/schedule/reshuffle", dependencies=[Depends(verify_api_key)])
async def reshuffle_schedule_endpoint():
    """Dynamically reshuffles the 2-run daily schedule to new random times with a 12-hour gap."""
    time1, time2 = reshuffle_schedule()
    return {
        "success": True,
        "message": "Daily pipeline schedule reshuffled successfully.",
        "scheduled_daily_runs": [time1, time2],
        "schedule_interval": "12 hours (2 runs per day)"
    }

@app.post("/api/v1/cleanup/temp", dependencies=[Depends(verify_api_key)])
async def cleanup_temp_endpoint():
    """Forces an immediate sweep and purge of files in the temp directory."""
    deleted = await asyncio.to_thread(clean_temp_directory, max_age_seconds=0)
    return {"success": True, "files_purged": deleted}

@app.post("/api/v1/push/test", dependencies=[Depends(verify_api_key)])
async def test_push_endpoint(req: PushTestRequest):
    """Broadcasts a test push notification to mobile app devices via Firebase FCM."""
    from service.notifications.push_service import send_push_notification
    success = await asyncio.to_thread(
        send_push_notification,
        title=req.title,
        body=req.body,
        post_id=req.post_id,
        topic=req.topic
    )
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to dispatch Firebase push notification. Check service account credentials."
        )
    return {
        "success": True,
        "message": "FCM push notification broadcasted successfully to topic.",
        "topic": req.topic,
        "title": req.title,
        "post_id": req.post_id
    }

@app.post("/api/v1/auth/rotate-key")
async def rotate_key_endpoint(req: RotateKeyRequest, request: Request):
    """Regenerates the system API secret key authenticated by master password, immediately revoking the old key."""
    global API_SECRET_KEY
    client_ip = request.client.host if request.client else "unknown"

    if req.master_password != MASTER_PASSWORD:
        logging.warning(
            f"[Security Alert] Unauthorized API key rotation attempt from {client_ip} rejected! Invalid master password."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid master password."
        )

    new_key = f"lt_sec_{secrets.token_hex(16)}"
    API_SECRET_KEY = new_key
    os.environ["API_SECRET_KEY"] = new_key
    update_env_api_key(new_key)

    logging.info(
        f"[Security] API secret key regenerated and rotated successfully from {client_ip}. Old key revoked immediately."
    )
    return {
        "success": True,
        "new_api_key": new_key,
        "message": "API key successfully rotated and old key invalidated."
    }
