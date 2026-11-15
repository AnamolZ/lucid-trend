import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
TEMP_DIR = ROOT_DIR / "temp"

DATA_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = ROOT_DIR / ".env"
load_dotenv(ENV_FILE)
load_dotenv()

PROFILES_FILE = DATA_DIR / "profiles.txt"
INTEL_DB_FILE = DATA_DIR / "instagram_intel.db"
OUTPUT_JSON_FILE = DATA_DIR / "latest_news_digest.json"

INSTAGRAM_USER = os.getenv("INSTAGRAM_USER", "scrapy0702")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
INSTAGRAM_SESSIONID = os.getenv("INSTAGRAM_SESSIONID", "").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-super-vl:free").strip()

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
