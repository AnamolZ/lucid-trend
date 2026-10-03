import os
import re
import logging
from logging.handlers import RotatingFileHandler

class GeminiLogFilter(logging.Filter):
    """
    Transforms raw HTTP transport logs from httpx and Google GenAI into clean,
    detailed, professional status messages, suppressing raw noise and internal transport dumps.
    """
    def filter(self, record):
        msg = record.getMessage()

        # Suppress routine internal ADK connection dumps
        if any(noise in msg for noise in [
            "Sending out request, model:",
            "Connecting to live for model:",
            "Response received from the model.",
            "Both GOOGLE_API_KEY and GEMINI_API_KEY are set"
        ]):
            return False

        # Handle 429 Too Many Requests (Rate limit / Quota)
        if "429" in msg and ("generativelanguage" in msg or "gemini" in msg.lower()):
            model_match = re.search(r"models/([^:\"]+)", msg)
            model_name = model_match.group(1) if model_match else "Gemini API"
            record.msg = f"[Rate Limit Alert] RPM/Quota limit reached on '{model_name}'. Initiating automatic failover..."
            record.args = ()
            record.levelno = logging.INFO
            record.levelname = "INFO"
            return True

        # Handle 503 Service Unavailable / Overloaded
        if "503" in msg and ("generativelanguage" in msg or "gemini" in msg.lower()):
            record.msg = "[Service Alert] Gemini server temporarily busy (503). Applying exponential backoff..."
            record.args = ()
            record.levelno = logging.INFO
            record.levelname = "INFO"
            return True

        # Handle 403 Forbidden / Project Denied
        if "403" in msg and ("generativelanguage" in msg or "gemini" in msg.lower()):
            record.msg = "[Auth Alert] API key lacks permissions or project disabled (403). Blacklisting key and rotating..."
            record.args = ()
            record.levelno = logging.WARNING
            record.levelname = "WARNING"
            return True

        # Suppress routine 200 OK transport lines
        if "HTTP Request:" in msg and "generativelanguage" in msg:
            if any(ok_code in msg for ok_code in ["200 OK", "200", "304"]):
                return False

        return True

def setup_logging():
    """
    Configures application-wide logging:
    1. Console output with clean formatting.
    2. Combined log file: logs/app.log (all messages >= INFO).
    3. Error-only log file: logs/error.log (all messages >= ERROR).
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)

    app_log_file = os.path.join(log_dir, "app.log")
    error_log_file = os.path.join(log_dir, "error.log")

    log_format = "%(asctime)s | %(levelname)-7s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers to prevent duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. Combined App File Handler (Rotating: 10 MB, up to 5 backups)
    app_file_handler = RotatingFileHandler(
        app_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    app_file_handler.setLevel(logging.INFO)
    app_file_handler.setFormatter(formatter)
    root_logger.addHandler(app_file_handler)

    # 3. Error-Only File Handler (Rotating: 10 MB, up to 5 backups)
    error_file_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    root_logger.addHandler(error_file_handler)

    # Attach filter to handlers
    gemini_filter = GeminiLogFilter()
    for h in root_logger.handlers:
        h.addFilter(gemini_filter)

    for logger_name in ["httpx", "httpcore", "google_genai", "google.adk", "google.adk.models.google_llm"]:
        log = logging.getLogger(logger_name)
        log.addFilter(gemini_filter)

    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("google_genai.types").setLevel(logging.ERROR)
    logging.getLogger("google.adk.models.google_llm").setLevel(logging.WARNING)
    logging.getLogger("google.adk").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
