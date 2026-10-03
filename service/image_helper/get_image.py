"""Hugging Face FLUX.1 image synthesis client with multi-key rotation and retry ladders."""

import io
import os
import time
import base64
import logging
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

class HuggingFaceKeyCoordinator:
    """Coordinates key rotation, retry cycles, and backoff pauses for FLUX.1 generation."""

    def __init__(self):
        self.bad_keys = set()
        self.key_index = 0

    def get_tokens(self, token_hint: str = None) -> list:
        """Parses and deduplicates Hugging Face access tokens from parameters and environment."""
        raw = []
        if token_hint:
            raw.extend(token_hint.split(","))
        env_tokens = (
            os.getenv("HUGGING_FACE_TOKENS")
            or os.getenv("HUGGING_FACE_TOKEN")
            or os.getenv("HF_TOKEN")
            or ""
        )
        if env_tokens:
            raw.extend(env_tokens.split(","))

        # Preserve insertion order while eliminating duplicates
        seen = set()
        cleaned = []
        for t in raw:
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                cleaned.append(t)
        return cleaned

    def generate_image(self, prompt: str, token_hint: str = None, max_rounds: int = 3, wait_seconds: int = 300) -> str:
        """Generates a PNG image via FLUX.1-schnell, rotating through active keys with backoff pauses."""
        tokens = self.get_tokens(token_hint)
        if not tokens:
            logging.error("[HuggingFace] No Hugging Face tokens configured in environment.")
            return None

        for round_num in range(1, max_rounds + 1):
            active_tokens = [k for k in tokens if k not in self.bad_keys]
            if not active_tokens:
                logging.warning("[HuggingFace] All keys were marked bad; resetting key pool for retry.")
                self.bad_keys.clear()
                active_tokens = tokens

            total_keys = len(active_tokens)
            start_idx = self.key_index % total_keys

            logging.info(
                f"[HuggingFace] Starting generation attempt (Round {round_num}/{max_rounds}) across {total_keys} active keys..."
            )

            # Iterate sequentially through available keys in current round
            for offset in range(total_keys):
                idx = (start_idx + offset) % total_keys
                token = active_tokens[idx]
                masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
                key_pos = tokens.index(token) + 1

                try:
                    logging.info(
                        f"[HuggingFace] (Round {round_num}/{max_rounds}) Requesting FLUX.1-schnell with Key #{key_pos} ({masked})..."
                    )
                    client = InferenceClient(token=token)
                    image = client.text_to_image(
                        prompt=prompt,
                        model="black-forest-labs/FLUX.1-schnell"
                    )
                    buf = io.BytesIO()
                    image.save(buf, format="PNG")
                    buf.seek(0)
                    encoded = base64.b64encode(buf.read()).decode("utf-8")

                    self.key_index = idx
                    logging.info(
                        f"[HuggingFace] Generated image successfully via FLUX.1-schnell (Key #{key_pos})."
                    )
                    return f"data:image/png;base64,{encoded}"

                except Exception as e:
                    err_msg = str(e)
                    logging.warning(
                        f"[HuggingFace] Key #{key_pos} ({masked}) failed in Round {round_num}: {err_msg}"
                    )
                    if any(code in err_msg for code in ["401", "403", "Invalid username or password"]):
                        self.bad_keys.add(token)

                    if offset < total_keys - 1:
                        next_idx = (start_idx + offset + 1) % total_keys
                        next_token = active_tokens[next_idx]
                        next_masked = next_token[:6] + "..." + next_token[-4:] if len(next_token) > 10 else "***"
                        logging.info(
                            f"[HuggingFace Failover] Switching to Key #{tokens.index(next_token) + 1} ({next_masked})..."
                        )

            # Apply backoff pause between exhaustion rounds
            if round_num < max_rounds:
                logging.warning(
                    f"[HuggingFace Backoff] All {total_keys} keys exhausted in Round {round_num}. "
                    f"Pausing {wait_seconds}s (5 mins) before Round {round_num + 1}/{max_rounds}..."
                )
                time.sleep(wait_seconds)
            else:
                logging.error(
                    f"[HuggingFace Exhaustion] All keys exhausted after {max_rounds} full rounds (with 5-minute backoff pauses). "
                    "Returning None to retain default image."
                )

        return None

hf_coordinator = HuggingFaceKeyCoordinator()

def huggingface_image(hf_token: str = None, prompt: str = None, max_rounds: int = 3, wait_seconds: int = 300) -> str:
    """Generates an image via FLUX.1-schnell with key rotation and backoff ladder, returning data URI."""
    if prompt is None and hf_token is not None:
        prompt = hf_token
        hf_token = None

    return hf_coordinator.generate_image(
        prompt=prompt,
        token_hint=hf_token,
        max_rounds=max_rounds,
        wait_seconds=wait_seconds
    )