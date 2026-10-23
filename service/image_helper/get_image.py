"""Unified high-precision image synthesis client with multi-provider cascade:
1. Cloudflare Workers AI Account Pool (Multi-account rotation with FLUX and SDXL-Lightning)
2. Hugging Face Inference API (black-forest-labs/FLUX.1-schnell key pool)
3. Pollinations.ai FLUX (High-Res 16:9 Zero-Auth Infinite Online Fallback)

Includes automated prompt grounding to guarantee photorealistic, post-specific scenes.
"""

import io
import os
import re
import time
import json
import random
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

    # Concrete visual scene anchors based on technical & financial domains
    if any(k in text_corpus for k in ["bitcoin", "crypto", "ethereum", "blockchain", "solana", "stablecoin", "usdc", "usdt", "defi", "web3"]):
        anchor = f"Futuristic high-tech cryptocurrency institutional treasury operations center with holographic cryptographic lattice visualizers, high-frequency liquidity telemetry terminals, dark polished reflective obsidian interior. Topic: {title or 'Crypto Infrastructure'}"
    elif any(k in text_corpus for k in ["swift", "banking", "treasury", "settlement", "liquidity", "forex", "etf", "capital", "inflation", "bond", "yield", "fed", "macroeconomic"]):
        anchor = f"Panoramic multinational enterprise corporate treasury trading floor overlooking city skyline at dusk, multi-display financial terminals showing real-time global capital flow heatmaps and order books, clean corporate cinematic lighting. Topic: {title or 'Financial Architecture'}"
    elif any(k in text_corpus for k in ["geopolitics", "diplomacy", "treaty", "sanctions", "sovereignty", "nato", "summit"]):
        anchor = f"Distinguished international summit press assembly hall with state flags, architectural walnut dais, press broadcast lighting, high-level geopolitical delegation setting. Topic: {title or 'Global Geopolitics'}"
    elif any(k in text_corpus for k in ["quantum", "qubit", "cryostat", "superconductor"]):
        anchor = f"Gleaming dilution refrigerator cryostat with gold-plated thermal plates and braided copper wiring inside an advanced quantum computing cleanroom laboratory, laser diagnostics. Topic: {title or 'Quantum Breakthrough'}"
    elif any(k in text_corpus for k in ["math", "formal proof", "theorem", "reasoning", "symbolic", "verification"]):
        anchor = f"High-tech mathematical supercomputing laboratory with illuminated panoramic blackboards displaying formal mathematical logic equations and topological diagrams, operator workstations with high-res monitors. Topic: {title or 'Mathematical Reasoning'}"
    elif any(k in text_corpus for k in ["chip", "semiconductor", "gpu", "tpu", "hardware", "nvidia", "silicon", "transistor", "dram"]):
        anchor = f"Macro photography of a high-performance silicon AI accelerator processor die, glowing etched nano-circuits, gold interconnect pins, liquid cooling pipes. Topic: {title or 'Hardware Architecture'}"
    elif bool(re.search(r'\b(code|developer|ide|compiler|rust|python|software|api|framework|library)\b', text_corpus)):
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
    if title and title.strip().lower() not in base.lower():
        base = f"{base}. Focus: {title.strip()}"

    style_suffix = "cinematic lighting, photorealistic, 8k octane render, clean 16:9 composition, hyper-detailed"
    if "16:9" not in base.lower():
        base = f"{base}, {style_suffix}"

    return base


class CloudflareAccountCoordinator:
    """Coordinates account rotation, cooldowns, and multi-model fallback across multiple Cloudflare accounts."""

    def __init__(self):
        self.bad_accounts = {}  # account_id -> cooldown_timestamp
        self.account_index = 0

    def get_accounts(self) -> list:
        """Parses and deduplicates Cloudflare (account_id, api_token) pairs from environment."""
        accounts = []

        # 1. Primary: Pair syntax 'account_id_1:token_1,account_id_2:token_2'
        raw_accounts = os.getenv("CLOUDFLARE_ACCOUNTS", "").strip()
        if raw_accounts:
            for item in raw_accounts.split(","):
                item = item.strip()
                if ":" in item:
                    acc_id, token = item.split(":", 1)
                    if acc_id.strip() and token.strip():
                        accounts.append((acc_id.strip(), token.strip()))

        # 2. Secondary: Comma-separated parallel lists
        acc_ids = [x.strip() for x in (os.getenv("CLOUDFLARE_ACCOUNT_IDS") or "").split(",") if x.strip()]
        tokens = [x.strip() for x in (os.getenv("CLOUDFLARE_API_TOKENS") or "").split(",") if x.strip()]
        if acc_ids and tokens:
            for acc_id, tok in zip(acc_ids, tokens):
                accounts.append((acc_id, tok))

        # 3. Legacy single account variables
        single_acc = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
        single_tok = (os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CLOUDFLARE_API_KEY") or "").strip()
        if single_acc and single_tok:
            accounts.append((single_acc, single_tok))

        # Deduplicate preserving discovery order
        seen = set()
        unique = []
        for acc_id, tok in accounts:
            if acc_id not in seen:
                seen.add(acc_id)
                unique.append((acc_id, tok))
        return unique

    def generate_image(self, prompt: str) -> str:
        """Cycles through active Cloudflare accounts. If FLUX is throttled, also tries SDXL-Lightning before failing over."""
        accounts = self.get_accounts()
        if not accounts:
            return None

        # Expire cooldowns older than 4 hours
        now = time.time()
        self.bad_accounts = {acc: ts for acc, ts in self.bad_accounts.items() if now - ts < 14400}

        active_accounts = [acc for acc in accounts if acc[0] not in self.bad_accounts]
        if not active_accounts:
            logging.info("[Cloudflare Coordinator] All Cloudflare accounts currently on cooldown / quota exhaustion.")
            return None

        total_active = len(active_accounts)
        start_idx = self.account_index % total_active

        # Multi-model cascade within Cloudflare: FLUX first, then high-efficiency SDXL-Lightning
        models = [
            ("@cf/black-forest-labs/flux-1-schnell", 4),
            ("@cf/bytedance/stable-diffusion-xl-lightning", 4)
        ]

        for offset in range(total_active):
            idx = (start_idx + offset) % total_active
            account_id, api_token = active_accounts[idx]
            masked_acc = account_id[:6] + "..." + account_id[-4:] if len(account_id) > 10 else account_id
            acc_num = accounts.index((account_id, api_token)) + 1

            for model_path, steps in models:
                model_name = model_path.split("/")[-1]
                url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_path}"
                headers = {
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "LucidTrend/1.0"
                }
                payload = json.dumps({"prompt": prompt, "steps": steps}).encode("utf-8")

                try:
                    logging.info(f"[Cloudflare Coordinator] Requesting {model_name} with Account #{acc_num} ({masked_acc})...")
                    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        content_type = resp.headers.get("Content-Type", "")
                        data = resp.read()
                        if "application/json" in content_type:
                            res_data = json.loads(data.decode("utf-8"))
                            image_b64 = res_data.get("result", {}).get("image")
                            if image_b64:
                                logging.info(f"[Cloudflare Coordinator] Successfully generated {model_name} via Account #{acc_num}.")
                                self.account_index = idx
                                return f"data:image/jpeg;base64,{image_b64}"
                        elif "image" in content_type or len(data) > 1000:
                            encoded = base64.b64encode(data).decode("utf-8")
                            mime = content_type if "image" in content_type else "image/jpeg"
                            logging.info(f"[Cloudflare Coordinator] Successfully generated {model_name} ({len(data)} bytes) via Account #{acc_num}.")
                            self.account_index = idx
                            return f"data:{mime};base64,{encoded}"

                    logging.warning(f"[Cloudflare Coordinator] Account #{acc_num} returned empty image data.")
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8", errors="replace")[:250]
                    logging.warning(f"[Cloudflare Coordinator] Account #{acc_num} HTTP {e.code}: {err_body}")
                    # If quota exhausted (429, 400 with limits, or 401/403 auth error), mark this account on cooldown
                    if e.code in (429, 401, 403) or any(w in err_body.lower() for w in ["limit", "neuron", "quota", "exceeded"]):
                        self.bad_accounts[account_id] = time.time()
                        break  # Break inner model loop, switch to next account
                except Exception as e:
                    logging.warning(f"[Cloudflare Coordinator] Account #{acc_num} request failed: {e}")

        return None


cf_coordinator = CloudflareAccountCoordinator()


def generate_cloudflare_image(prompt: str) -> str:
    """Generates an image via Cloudflare Workers AI Account Pool."""
    return cf_coordinator.generate_image(prompt)


def generate_pollinations_image(prompt: str) -> str:
    """Generates a high-quality technical image via Pollinations.ai (infinite zero-auth online AI fallback)."""
    clean_prompt = urllib.parse.quote(prompt.strip())
    pollen_key = os.getenv("POLLINATIONS_API_KEY") or os.getenv("POLLEN_API_KEY")

    seed = random.randint(1, 9999999)
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1280&height=720&model=flux&nologo=true&seed={seed}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if pollen_key:
        headers["Authorization"] = f"Bearer {pollen_key.strip()}"

    for attempt in range(1, 4):
        try:
            logging.info(f"[Pollinations] Dispatching online AI generation (Attempt #{attempt})...")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = resp.read()
                if len(data) > 1000:
                    encoded = base64.b64encode(data).decode("utf-8")
                    logging.info(f"[Pollinations] Successfully generated online AI image ({len(data)} bytes).")
                    return f"data:image/jpeg;base64,{encoded}"

            logging.warning("[Pollinations] Response contained invalid or empty image data.")
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")[:150]
            logging.warning(f"[Pollinations] HTTP {he.code}: {err_body}")
            if attempt == 2:
                # Failover to turbo model on Pollinations if FLUX is heavily congested
                url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1280&height=720&model=turbo&nologo=true&seed={seed}"
            time.sleep(4)
        except Exception as e:
            logging.warning(f"[Pollinations] Generation attempt #{attempt} failed: {e}")
            if attempt < 3:
                time.sleep(3)

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
    """Universal online image generation entry point with story grounding and multi-provider cascade.

    Cascade Priority:
    1. Cloudflare Workers AI Account Pool (Multi-account rotation with FLUX and SDXL-Lightning)
    2. Hugging Face FLUX.1-schnell (if active credits exist)
    3. Pollinations.ai FLUX (High-Res 16:9 Zero-Auth Infinite Online Fallback)
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

    # Tier 1: Cloudflare Workers AI Account Pool (Cycles through all accounts)
    cf_img = cf_coordinator.generate_image(effective_prompt)
    if cf_img:
        return cf_img

    # Tier 2: Hugging Face FLUX (rotates keys, fails fast if credits exhausted)
    hf_img = hf_coordinator.generate_image(
        prompt=effective_prompt,
        token_hint=hf_token,
        max_rounds=max_rounds,
        wait_seconds=wait_seconds
    )
    if hf_img:
        return hf_img

    # Tier 3: Pollinations.ai FLUX Online Fallback (Infinite, 100% online AI)
    fallback_img = generate_pollinations_image(effective_prompt)
    if fallback_img:
        return fallback_img

    return None