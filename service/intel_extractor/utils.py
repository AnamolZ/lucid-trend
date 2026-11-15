import re
from typing import List
from config.settings import PROFILES_FILE


def clean_text(text: str) -> str:
    """Strip accessibility image descriptions, credits, and formatting junk."""
    if not text:
        return ""
    text = re.sub(r"[\u2060\u200b\ufeff\u00a0]", " ", text)
    patterns = [
        r"(?i)\bimage description\s*:.*?(?=(\n\s*\n|\Z))",
        r"(?i)\bphoto description\s*:.*?(?=(\n\s*\n|\Z))",
        r"(?i)\bvisual description\s*:.*?(?=(\n\s*\n|\Z))",
        r"(?i)\bimage credit\s*:.*?(?=(\n\s*\n|\Z))",
        r"(?i)\bphoto credit\s*:.*?(?=(\n\s*\n|\Z))",
        r"(?i)\bpicture credit\s*:.*?(?=(\n\s*\n|\Z))",
        r"(?i)\bphoto by\s*:.*?(?=(\n\s*\n|\Z))",
        r"(?i)\bphotographer\s*:.*?(?=(\n\s*\n|\Z))",
        r"(?i)\bcredit\s*:.*?(?=(\n\s*\n|\Z))",
        r"(?i)\balt text\s*:.*?(?=(\n\s*\n|\Z))",
    ]
    for p in patterns:
        text = re.sub(p, "", text, flags=re.DOTALL)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def normalize_username(url_or_handle: str) -> str:
    """Normalize input URL or handle into a clean Instagram username."""
    cleaned = url_or_handle.strip()
    match = re.search(r"instagram\.com/([^/?#]+)", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1)
    return cleaned.lstrip("@").strip().lower()


def load_profiles() -> List[str]:
    """Read target profiles from data/profiles.txt."""
    if not PROFILES_FILE.exists():
        return []
    profiles = []
    with open(PROFILES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                user = normalize_username(line)
                if user and user not in profiles:
                    profiles.append(user)
    return profiles
