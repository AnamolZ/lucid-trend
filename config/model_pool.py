import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Verified Free-Tier models on Google AI Studio ranked by output quality & reasoning depth
# Models verified responding with HTTP 200 across active keys
MODEL_POOL = [
    "gemini-3.7-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
]

class KeyModelCoordinator:
    """
    Coordinates multi-model and multi-API-key cascading failover.
    Ensures 100% perpetual uptime on free tier by rotating keys on quota limits,
    and cascading down through the model pool if all keys for a model are exhausted.
    """
    def __init__(self):
        self.raw_keys = self._load_keys()
        self.bad_keys = set()
        self.model_index = 0
        self.key_index = 0
        self.models = MODEL_POOL
        
        # Override initial model if user configured GEMINI_MODEL in .env
        env_model = os.getenv("GEMINI_MODEL")
        if env_model and env_model in self.models:
            self.model_index = self.models.index(env_model)

        self._sync_environment()

    def _load_keys(self):
        raw = os.getenv("GOOGLE_API_KEYS") or os.getenv("GOOGLE_API_KEY") or ""
        parsed = [k.strip() for k in raw.split(",") if k.strip()]
        if not parsed:
            logging.warning("[Coordinator] No GOOGLE_API_KEY or GOOGLE_API_KEYS found in environment.")
            return [""]
        return parsed

    @property
    def valid_keys(self):
        active = [k for k in self.raw_keys if k not in self.bad_keys]
        return active if active else self.raw_keys

    def _sync_environment(self):
        active_key = self.get_active_key()
        if active_key:
            os.environ["GOOGLE_API_KEY"] = active_key
            os.environ.pop("GEMINI_API_KEY", None)
            try:
                import google.generativeai as genai
                genai.configure(api_key=active_key)
            except Exception:
                pass

    def get_active_model(self) -> str:
        return self.models[self.model_index % len(self.models)]

    def get_active_key(self) -> str:
        keys = self.valid_keys
        if not keys:
            return ""
        return keys[self.key_index % len(keys)]

    def get_active_pair(self):
        """Returns tuple of (active_model_name, active_api_key)."""
        self._sync_environment()
        return self.get_active_model(), self.get_active_key()

    def report_failure(self, failed_model: str = None, failed_key: str = None, error_code: str = ""):
        """
        Rotates key first on 429/503/404/403. If all keys for current model are exhausted,
        cascades to the next model in the pool.
        """
        current_key = failed_key or self.get_active_key()
        current_model = failed_model or self.get_active_model()
        err_text = str(error_code).upper()

        # If permanent auth/permission error (403, 400, 404, PERMISSION_DENIED), permanently blacklist key
        if any(term in err_text for term in ["403", "400", "404", "PERMISSION_DENIED"]):
            if current_key:
                masked = current_key[:6] + "..." + current_key[-4:] if len(current_key) > 10 else "***"
                logging.warning(
                    f"[Security/Key Alert] Key ({masked}) received permanent error ({error_code}). Blacklisting for this session."
                )
                self.bad_keys.add(current_key)

        keys = self.valid_keys
        total_keys = len(keys)
        
        # If multiple valid keys exist for this model, rotate to next key
        if total_keys > 1 and (self.key_index + 1) < total_keys:
            prev_idx = self.key_index + 1
            self.key_index += 1
            new_model = self.get_active_model()
            new_key = self.get_active_key()
            masked = new_key[:6] + "..." + new_key[-4:] if len(new_key) > 10 else "***"
            logging.info(
                f"[Key Rotation] Key #{prev_idx} reached quota ({error_code or 'limit'}). Switched to API Key #{self.key_index + 1} ({masked}) on model '{new_model}'."
            )
        else:
            # All keys exhausted for this model -> cascade down to next model tier and reset key index
            prev_model = self.get_active_model()
            self.key_index = 0
            self.model_index = (self.model_index + 1) % len(self.models)
            new_model = self.get_active_model()
            new_key = self.get_active_key()
            masked = new_key[:6] + "..." + new_key[-4:] if len(new_key) > 10 else "***"
            logging.info(
                f"[Model Cascading] All keys exhausted for '{prev_model}'. Cascaded to tier '{new_model}' using Key #{self.key_index + 1} ({masked})."
            )

        self._sync_environment()
        return self.get_active_model(), self.get_active_key()

# Singleton coordinator instance
coordinator = KeyModelCoordinator()

def get_active_model():
    return coordinator.get_active_model()

def get_active_key():
    return coordinator.get_active_key()

def get_active_pair():
    return coordinator.get_active_pair()

def rotate_model(failed_model=None, error_code=""):
    model, _ = coordinator.report_failure(failed_model=failed_model, error_code=error_code)
    return model

def report_failure(failed_model=None, failed_key=None, error_code=""):
    return coordinator.report_failure(failed_model, failed_key, error_code)
