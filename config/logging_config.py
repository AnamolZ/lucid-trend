import re
import logging

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
    """Configures application-wide logging with clean timestamps and filter attachments."""
    root_logger = logging.getLogger()
    
    # Configure root format if not already configured
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        root_logger.setLevel(logging.INFO)
        for h in root_logger.handlers:
            h.setFormatter(logging.Formatter(
                fmt="%(asctime)s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))

    # Attach filter to root and third-party loggers
    gemini_filter = GeminiLogFilter()
    root_logger.addFilter(gemini_filter)
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
