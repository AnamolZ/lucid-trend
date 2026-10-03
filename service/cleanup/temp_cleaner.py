import os
import time
import logging

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp")

def ensure_temp_dir():
    """Ensures that the temp directory exists."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    return TEMP_DIR

def clean_temp_directory(max_age_seconds: int = 3600):
    """
    Cleans up files in the temp directory older than max_age_seconds (default 1 hour).
    If max_age_seconds is 0, purges all files in the directory.
    """
    if not os.path.exists(TEMP_DIR):
        return 0

    now = time.time()
    deleted_count = 0

    for filename in os.listdir(TEMP_DIR):
        file_path = os.path.join(TEMP_DIR, filename)
        if os.path.isfile(file_path):
            try:
                file_age = now - os.path.getmtime(file_path)
                if max_age_seconds == 0 or file_age >= max_age_seconds:
                    os.remove(file_path)
                    deleted_count += 1
                    logging.info(f"[TempCleaner] Removed expired temporary file: {filename}")
            except Exception as e:
                logging.warning(f"[TempCleaner] Failed to remove temp file '{filename}': {e}")

    if deleted_count > 0:
        logging.info(f"[TempCleaner] Auto-cleanup complete. Cleared {deleted_count} files from '{TEMP_DIR}'.")
    return deleted_count
