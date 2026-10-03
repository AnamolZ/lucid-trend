"""Manages Gemini model tier cascading and API key rotation for free-tier resilience."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

MODEL_POOL = [
    "gemini-3.7-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
]

class KeyModelCoordinator:
    """Coordinates API key rotation and model tier cascading upon quota exhaustion."""

    def __init__(self):
        self.raw_keys = self._load_keys()
        self.bad_keys = set()
        self.model_index = 0
        self.key_index = 0
        self.models = MODEL_POOL

        env_model = os.getenv("GEMINI_MODEL")
        if env_model and env_model in self.models:
            self.model_index = self.models.index(env_model)

        self._sync_environment()

    def _load_keys(self) -> list:
        raw = os.getenv("GOOGLE_API_KEYS") or os.getenv("GOOGLE_API_KEY") or ""
        parsed = [k.strip() for k in raw.split(",") if k.strip()]
        if not parsed:
            logging.warning("[Coordinator] No GOOGLE_API_KEY or GOOGLE_API_KEYS found in environment.")
            return [""]
        return parsed

    @property
    def valid_keys(self) -> list:
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
        """Returns the currently active Gemini model name."""
        return self.models[self.model_index % len(self.models)]

    def get_active_key(self) -> str:
        """Returns the currently active API key."""
        keys = self.valid_keys
        if not keys:
            return ""
        return keys[self.key_index % len(keys)]

    def get_active_pair(self) -> tuple:
        """Returns the current active model name and API key pair."""
        self._sync_environment()
        return self.get_active_model(), self.get_active_key()

    def report_failure(self, failed_model: str = None, failed_key: str = None, error_code: str = "") -> tuple:
        """Rotates active key or cascades to the next model tier upon failure."""
        current_key = failed_key or self.get_active_key()
        current_model = failed_model or self.get_active_model()
        err_text = str(error_code).upper()

        # Blacklist key permanently for this session on authentication or project permission failures
        if any(term in err_text for term in ["403", "400", "404", "PERMISSION_DENIED"]):
            if current_key:
                masked = current_key[:6] + "..." + current_key[-4:] if len(current_key) > 10 else "***"
                logging.warning(
                    f"[Security/Key Alert] Key ({masked}) received permanent error ({error_code}). Blacklisting for this session."
                )
                self.bad_keys.add(current_key)

        keys = self.valid_keys
        total_keys = len(keys)

        # Rotate to the next available API key within the current model tier
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
            # Cascade down to the next model tier when all keys for the current model are exhausted
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

coordinator = KeyModelCoordinator()

def get_active_model() -> str:
    """Retrieves the active model identifier."""
    return coordinator.get_active_model()

def get_active_key() -> str:
    """Retrieves the active API key."""
    return coordinator.get_active_key()

def get_active_pair() -> tuple:
    """Retrieves the active model and API key pair."""
    return coordinator.get_active_pair()

def rotate_model(failed_model=None, error_code="") -> str:
    """Triggers failover and returns the newly active model."""
    model, _ = coordinator.report_failure(failed_model=failed_model, error_code=error_code)
    return model

def report_failure(failed_model=None, failed_key=None, error_code="") -> tuple:
    """Reports a failure to the coordinator to trigger failover."""
    return coordinator.report_failure(failed_model, failed_key, error_code)
