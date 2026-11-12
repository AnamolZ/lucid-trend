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


_AI_SLOP_CLICHES = (
    "glowing semantic code graph",
    "abstract api nodes",
    "floating abstract",
    "expansive digital space",
    "dots and lines",
    "in mid-air above",
    "abstract formal proof code",
    "holographic",
    "digital illustration",
    "concept art",
    "octane render",
    "unreal engine",
    "cyberpunk",
    "sci-fi fantasy",
    "futuristic hologram",
)

_SLOP_TOKEN_RE = re.compile(
    r"\b(8k|4k|octane\s*render|unreal\s*engine|hyper-?detailed|hyper-?realistic|photorealistic|"
    r"cinematic\s+lighting|cinematic\s+digital\s+illustration|digital\s+illustration|"
    r"concept\s+art|3d\s+render|holographic|hologram|futuristic|sci-?fi|cyberpunk|"
    r"neon\s+glow|glowing\s+neon|obsidian|masterpiece|trending\s+on\s+artstation)\b",
    re.IGNORECASE,
)


def _scrub_slop_phrases(text: str) -> str:
    """Removes CGI, 3D-render, and buzzword triggers that cause synthetic AI visuals."""
    cleaned = _SLOP_TOKEN_RE.sub("", text or "")
    cleaned = re.sub(r"\s*,\s*,+", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.-")
    return cleaned


def build_grounded_flux_prompt(
    prompt: str = None,
    title: str = None,
    description: str = None,
    category: list = None
) -> str:
    """Grounds image prompts in real-world documentary photojournalism instead of synthetic CGI."""
    text_corpus = f"{title or ''} {description or ''} {prompt or ''}".lower()

    raw_prompt = (prompt or "").strip()
    is_abstract_cliche = any(cliche in raw_prompt.lower() for cliche in _AI_SLOP_CLICHES)

    # Concrete, real-world editorial press photography anchors per beat (no CGI/hologram tropes)
    if any(k in text_corpus for k in ["bitcoin", "crypto", "ethereum", "blockchain", "solana", "stablecoin", "usdc", "usdt", "defi", "web3"]):
        anchor = f"Editorial documentary photograph inside a modern institutional digital-asset research office in Zurich or New York, analysts at standard dual-monitor workstations reviewing market order books and hardware security modules under natural daylight through blinds. Subject: {title or 'Crypto Market Structure'}"
    elif any(k in text_corpus for k in ["swift", "banking", "treasury", "settlement", "liquidity", "forex", "etf", "capital", "inflation", "bond", "yield", "fed", "macroeconomic", "tariff", "central bank"]):
        anchor = f"Reuters-style documentary photograph of an active institutional trading desk or central bank press corridor, brokers in business attire checking multi-screen financial charts in natural daytime lighting, subtle ambient glass reflections. Subject: {title or 'Global Markets'}"
    elif any(k in text_corpus for k in ["geopolitics", "diplomacy", "treaty", "sanctions", "sovereignty", "nato", "summit", "defense", "maritime", "military", "border"]):
        anchor = f"Associated Press documentary photograph of an international diplomatic summit hall or strategic coastal corridor in overcast morning light, national flags, press briefing microphones on a wooden podium, shallow depth of field. Subject: {title or 'Geopolitical Affairs'}"
    elif any(k in text_corpus for k in ["quantum", "qubit", "cryostat", "superconductor"]):
        anchor = f"Documentary photograph inside an academic physics laboratory, researchers in casual lab coats inspecting a cylindrical brass and stainless-steel dilution refrigerator cryostat suspended from a rigid aluminum frame under white overhead fluorescent lights. Subject: {title or 'Quantum Hardware'}"
    elif any(k in text_corpus for k in ["math", "formal proof", "theorem", "reasoning", "symbolic", "verification"]):
        anchor = f"Candid documentary photograph in a university research seminar room, mathematicians standing near a chalk-smudged green blackboard covered in handwritten proofs, natural window light across wooden desks and open laptops. Subject: {title or 'Mathematical Research'}"
    elif any(k in text_corpus for k in ["chip", "semiconductor", "gpu", "tpu", "hardware", "nvidia", "silicon", "transistor", "dram", "wafer", "tsmc", "asml"]):
        anchor = f"Industrial photojournalism shot inside a real semiconductor cleanroom facility, engineers in white Tyvek bunny suits and safety goggles examining an iridescent bare silicon wafer beside stainless steel lithography machinery under even white cleanroom lighting. Subject: {title or 'Semiconductor Manufacturing'}"
    elif bool(re.search(r'\b(code|developer|ide|compiler|rust|python|software|api|framework|library|linux|kernel)\b', text_corpus)):
        anchor = f"Natural candid documentary photograph of a software engineer working on a matte laptop and external vertical monitor in a quiet daytime engineering office with potted plants and natural window light, unposed desk clutter, realistic keyboard and coffee mug. Subject: {title or 'Software Engineering'}"
    elif any(k in text_corpus for k in ["security", "vulnerability", "hack", "cyber", "malware", "firewall", "encryption", "zero-day"]):
        anchor = f"Real-world editorial photograph of an enterprise incident-response conference room, network security engineers reviewing log timelines on ordinary wall displays and laptops in neutral fluorescent office light. Subject: {title or 'Cybersecurity'}"
    elif any(k in text_corpus for k in ["robot", "humanoid", "autonomous", "drone", "actuator", "satellite", "aerospace", "rocket"]):
        anchor = f"Candid press photograph inside an industrial robotics and aerospace assembly bay, mechanical engineers with safety glasses and hand tools testing metal actuators and wiring harnesses on a brushed steel workbench under warehouse skylighting. Subject: {title or 'Robotics and Aerospace'}"
    elif any(k in text_corpus for k in ["datacenter", "cloud", "server", "cluster", "kubernetes", "infra", "ai model", "llm", "inference"]):
        anchor = f"Documentary photograph looking down a long industrial server aisle inside a working hyperscale data center, perforated grey steel cabinet doors, neat yellow fiber patch cables overhead, cool utilitarian aisle lighting, technician inspecting a rack in the background. Subject: {title or 'Compute Infrastructure'}"
    else:
        anchor = f"Candid editorial documentary photograph illustrating {title or 'current industry developments'}, authentic real-world workplace or industrial setting, natural ambient daylight, unposed photojournalistic framing"

    cleaned_prompt = _scrub_slop_phrases(raw_prompt)
    if cleaned_prompt and not is_abstract_cliche and len(cleaned_prompt) > 30:
        base = cleaned_prompt
    else:
        base = anchor

    base = base.replace('"', '').replace("'", "").strip()
    if title and title.strip().lower() not in base.lower():
        base = f"{base}. Subject: {title.strip()}"

    style_suffix = (
        "authentic Reuters press photograph, documentary photojournalism, shot on 35mm full-frame camera, "
        "35mm lens f/2.8, natural unretouched lighting, real-world textures, subtle film grain, balanced editorial full-frame composition"
    )
    return f"{base}, {style_suffix}"


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

        # Multi-model cascade within Cloudflare: FLUX (8 steps for sharp detail) first, then SDXL-Lightning
        models = [
            ("@cf/black-forest-labs/flux-1-schnell", 8),
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
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&model=flux&enhance=true&nologo=true&seed={seed}"
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
                url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&model=turbo&nologo=true&seed={seed}"
            time.sleep(4)
        except Exception as e:
            logging.warning(f"[Pollinations] Generation attempt #{attempt} failed: {e}")
            if attempt < 3:
                time.sleep(3)

    return None


def huggingface_image(
    hf_token: str = None,
    prompt: str = None,
    title: str = None,
    description: str = None,
    category: list = None,
    max_rounds: int = 1,
    wait_seconds: int = 0
) -> str:
    """Universal online image generation entry point with story grounding and Cloudflare AI pool.

    Cascade Priority:
    1. Cloudflare Workers AI Account Pool (Multi-account rotation with FLUX and SDXL-Lightning)
    2. Pollinations.ai FLUX (High-Res 16:9 Zero-Auth Infinite Online Fallback)
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

    # Tier 2: Pollinations.ai FLUX Online Fallback (Infinite, 100% online AI)
    fallback_img = generate_pollinations_image(effective_prompt)
    if fallback_img:
        return fallback_img

    return None