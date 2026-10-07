"""Unified high-precision image synthesis client with multi-provider cascade:
1. Cloudflare Workers AI (@cf/black-forest-labs/flux-1-schnell)
2. Hugging Face Inference API (black-forest-labs/FLUX.1-schnell)
3. Pollinations.ai FLUX (High-Res 16:9 Zero-Auth Fallback)

Includes automated prompt grounding to guarantee photorealistic, post-specific scenes.
"""

import io
import os
import time
import json
import base64
import logging
import urllib.request
import urllib.parse
import urllib.error
from dotenv import load_dotenv

load_dotenv()


def build_grounded_flux_prompt(
    prompt: str = None,
    title: str = None,
    description: str = None,
    category: list = None
) -> str:
    """Enriches and grounds image prompts to ensure concrete, photorealistic scenes directly matching the article."""
    text_corpus = f"{title or ''} {description or ''} {prompt or ''}".lower()

    # Detect abstract/cliche tropes that yield generic floating dots
    is_abstract_cliche = any(
        cliche in (prompt or "").lower() for cliche in [
            "glowing semantic code graph", "abstract api nodes",
            "floating abstract", "expansive digital space",
            "dots and lines", "in mid-air above", "abstract formal proof code"
        ]
    )

    # Concrete visual scene anchors based on technical domain
    if any(k in text_corpus for k in ["quantum", "qubit", "cryostat", "superconductor"]):
        anchor = f"Gleaming dilution refrigerator cryostat with gold-plated thermal plates and braided copper wiring inside an advanced quantum computing cleanroom laboratory, laser diagnostics. Topic: {title or 'Quantum Breakthrough'}"
    elif any(k in text_corpus for k in ["math", "formal proof", "theorem", "reasoning", "symbolic", "verification"]):
        anchor = f"High-tech mathematical supercomputing laboratory with illuminated panoramic blackboards displaying formal mathematical logic equations and topological diagrams, operator workstations with high-res monitors. Topic: {title or 'Mathematical Reasoning'}"
    elif any(k in text_corpus for k in ["chip", "semiconductor", "gpu", "tpu", "hardware", "nvidia", "silicon", "transistor"]):
        anchor = f"Macro photography of a high-performance silicon AI accelerator processor die, glowing etched nano-circuits, gold interconnect pins, liquid cooling pipes. Topic: {title or 'Hardware Architecture'}"
    elif any(k in text_corpus for k in ["code", "developer", "ide", "python", "framework", "library", "api", "software", "compiler", "rust"]):
        anchor = f"A senior software engineer at an ergonomic multi-monitor workstation in a modern architectural tech office at twilight, screens glowing with crisp IDE code syntax and terminal telemetry. Topic: {title or 'Developer Ecosystem'}"
    elif any(k in text_corpus for k in ["security", "vulnerability", "hack", "cyber", "malware", "firewall", "encryption"]):
        anchor = f"Panoramic high-tech cybersecurity operations center (SOC) with curved video walls projecting global network traffic telemetry, glowing server racks, analysts at command consoles. Topic: {title or 'Cybersecurity'}"
    elif any(k in text_corpus for k in ["robot", "humanoid", "autonomous", "drone", "actuator"]):
        anchor = f"Advanced collaborative robotic system with carbon fiber actuators being calibrated in an engineering research facility, ambient cinematic studio lighting. Topic: {title or 'Autonomous Robotics'}"
    elif any(k in text_corpus for k in ["datacenter", "cloud", "server", "cluster", "kubernetes", "infra"]):
        anchor = f"Cavernous enterprise cloud datacenter with towering server racks, pulsing blue and amber status LEDs, neatly organized fiber optic cabling, reflective polished dark floor. Topic: {title or 'Cloud Infrastructure'}"
    else:
        anchor = f"High-impact cinematic technological scene capturing {title or 'next-generation technology breakthrough'}, modern high-tech research facility, architectural lighting"

    if prompt and not is_abstract_cliche and len(prompt.strip()) > 30:
        base = prompt.strip()
    else:
        base = anchor

    base = base.replace('"', '').replace("'", "").strip()
    style_suffix = "cinematic lighting, photorealistic, 8k octane render, clean 16:9 composition, hyper-detailed"
    if "16:9" not in base.lower():
        base = f"{base}, {style_suffix}"

    return base


def generate_cloudflare_image(prompt: str) -> str:
    """Generates an image via Cloudflare Workers AI using @cf/black-forest-labs/flux-1-schnell."""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CLOUDFLARE_API_KEY")

    if not account_id or not api_token:
        return None

    account_id = account_id.strip()
    api_token = api_token.strip()

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "User-Agent": "LucidTrend/1.0"
    }
    payload = json.dumps({"prompt": prompt, "steps": 4}).encode("utf-8")

    try:
        masked_acc = account_id[:6] + "..." if len(account_id) > 6 else account_id
        logging.info(f"[Cloudflare Workers AI] Dispatching FLUX request for account '{masked_acc}'...")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=45) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            if "application/json" in content_type:
                res_data = json.loads(data.decode("utf-8"))
                image_b64 = res_data.get("result", {}).get("image")
                if image_b64:
                    logging.info("[Cloudflare Workers AI] Successfully generated FLUX image (Base64 JSON).")
                    return f"data:image/jpeg;base64,{image_b64}"
            elif "image" in content_type or len(data) > 1000:
                encoded = base64.b64encode(data).decode("utf-8")
                mime = content_type if "image" in content_type else "image/jpeg"
                logging.info(f"[Cloudflare Workers AI] Successfully generated FLUX image ({len(data)} bytes).")
                return f"data:{mime};base64,{encoded}"

        logging.warning("[Cloudflare Workers AI] Response contained no valid image data.")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:250]
        logging.warning(f"[Cloudflare Workers AI] HTTP {e.code}: {err_body}")
    except Exception as e:
        logging.warning(f"[Cloudflare Workers AI] Request failed: {e}")

    return None


def generate_pollinations_image(prompt: str) -> str:
    """Generates a high-quality 16:9 FLUX image via Pollinations.ai (zero-cost, zero-auth fallback)."""
    try:
        logging.info("[Pollinations FLUX] Dispatching fallback generation request...")
        clean_prompt = urllib.parse.quote(prompt.strip())
        url = f"https://image.pollinations.ai/prompt/{clean_prompt}?model=flux&width=1024&height=576&nologo=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = resp.read()
            if len(data) > 1000:
                encoded = base64.b64encode(data).decode("utf-8")
                logging.info(f"[Pollinations FLUX] Successfully generated fallback FLUX image ({len(data)} bytes).")
                return f"data:image/jpeg;base64,{encoded}"

        logging.warning("[Pollinations FLUX] Response contained invalid or empty image data.")
    except Exception as e:
        logging.warning(f"[Pollinations FLUX] Generation fallback failed: {e}")

    return None


class HuggingFaceKeyCoordinator:
    """Coordinates key rotation, retry cycles, and backoff pauses for FLUX.1 generation."""

    def __init__(self):
        self.bad_keys = {}  # token -> timestamp
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

        seen = set()
        cleaned = []
        for t in raw:
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                cleaned.append(t)
        return cleaned

    def generate_image(self, prompt: str, token_hint: str = None, max_rounds: int = 1, wait_seconds: int = 0) -> str:
        """Generates an image via FLUX.1-schnell, rotating through active keys."""
        tokens = self.get_tokens(token_hint)
        if not tokens:
            return None

        now = time.time()
        self.bad_keys = {k: ts for k, ts in self.bad_keys.items() if now - ts < 1800}

        active_tokens = [k for k in tokens if k not in self.bad_keys]
        if not active_tokens:
            logging.info("[HuggingFace] All HF tokens currently on cooldown due to quota exhaustion.")
            return None

        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            logging.warning("[HuggingFace] huggingface_hub package not installed.")
            return None

        for round_num in range(1, max_rounds + 1):
            active_tokens = [k for k in tokens if k not in self.bad_keys]
            if not active_tokens:
                break

            total_keys = len(active_tokens)
            start_idx = self.key_index % total_keys

            for offset in range(total_keys):
                idx = (start_idx + offset) % total_keys
                token = active_tokens[idx]
                masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
                key_pos = tokens.index(token) + 1

                try:
                    logging.info(f"[HuggingFace] Requesting FLUX.1 with Key #{key_pos} ({masked})...")
                    client = InferenceClient(token=token)
                    image = client.text_to_image(prompt=prompt, model="black-forest-labs/FLUX.1-schnell")
                    buf = io.BytesIO()
                    image.save(buf, format="PNG")
                    buf.seek(0)
                    encoded = base64.b64encode(buf.read()).decode("utf-8")

                    self.key_index = idx
                    logging.info(f"[HuggingFace] Generated image successfully via FLUX.1 (Key #{key_pos}).")
                    return f"data:image/png;base64,{encoded}"

                except Exception as e:
                    err_msg = str(e)
                    logging.warning(f"[HuggingFace] Key #{key_pos} failed: {err_msg}")
                    if any(code in err_msg for code in ["401", "402", "403", "Payment Required", "Invalid username or password"]):
                        self.bad_keys[token] = time.time()

            if round_num < max_rounds and wait_seconds > 0:
                time.sleep(wait_seconds)

        return None


hf_coordinator = HuggingFaceKeyCoordinator()


def huggingface_image(
    hf_token: str = None,
    prompt: str = None,
    title: str = None,
    description: str = None,
    category: list = None,
    max_rounds: int = 1,
    wait_seconds: int = 0
) -> str:
    """Universal image generation entry point with story grounding and multi-provider cascade.

    Cascade Priority:
    1. Cloudflare Workers AI FLUX (@cf/black-forest-labs/flux-1-schnell)
    2. Hugging Face FLUX.1-schnell (if active credits exist)
    3. Pollinations.ai FLUX (High-Res 16:9 Zero-Auth Fallback)
    """
    if prompt is None and hf_token is not None:
        prompt = hf_token
        hf_token = None

    effective_prompt = build_grounded_flux_prompt(
        prompt=prompt,
        title=title,
        description=description,
        category=category
    )

    if not effective_prompt:
        return None

    # Tier 1: Cloudflare Workers AI FLUX
    cf_account = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    cf_token = os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CLOUDFLARE_API_KEY")
    if cf_account and cf_token and cf_account.strip():
        img = generate_cloudflare_image(effective_prompt)
        if img:
            return img

    # Tier 2: Hugging Face FLUX (rotates keys, fails fast if credits exhausted)
    hf_img = hf_coordinator.generate_image(
        prompt=effective_prompt,
        token_hint=hf_token,
        max_rounds=max_rounds,
        wait_seconds=wait_seconds
    )
    if hf_img:
        return hf_img

    # Tier 3: Pollinations.ai FLUX Fallback
    fallback_img = generate_pollinations_image(effective_prompt)
    if fallback_img:
        return fallback_img

    return None