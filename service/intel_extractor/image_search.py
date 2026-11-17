import io
import re
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional
import requests
from PIL import Image
from duckduckgo_search import DDGS

from config.settings import TEMP_DIR, HTTP_HEADERS
from service.image_helper.get_image import CloudflareAccountCoordinator, build_grounded_flux_prompt, generate_pollinations_image
from service.intel_extractor.image_verifier import verify_image_relevance


def search_and_download_image(query: str, filename_prefix: str = "lead_thumbnail") -> Optional[Path]:
    clean_query = re.sub(r'["\']', '', query).strip()
    search_terms = f"{clean_query} press photo"

    print(f"[Image] Searching free web images for: '{clean_query}'...")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(search_terms, max_results=5, safesearch="on"))

        for res in results:
            img_url = res.get("image")
            if not img_url:
                continue

            try:
                resp = requests.get(img_url, headers=HTTP_HEADERS, timeout=12)
                resp.raise_for_status()

                with Image.open(io.BytesIO(resp.content)) as im:
                    if im.width >= 600 and im.height >= 350:
                        im_rgb = im.convert("RGB")
                        save_path = TEMP_DIR / f"{filename_prefix}.jpg"
                        im_rgb.save(save_path, "JPEG", quality=90)
                        print(f"[Image] Downloaded authentic press image to: {save_path}")
                        return save_path
            except Exception:
                continue
    except Exception as e:
        print(f"[Image] Web image search notice: {e}")

    return None


def search_wikimedia_image(query: str, filename_prefix: str = "lead_thumbnail") -> Optional[Path]:
    clean_query = re.sub(r'["\']', '', query).strip()
    words = clean_query.split()[:4]
    search_term = " ".join(words)

    url = (
        f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
        f"&gsrsearch={urllib.parse.quote(search_term)}&gsrnamespace=6&gsrlimit=3"
        f"&prop=imageinfo&iiprop=url|size|mime&format=json"
    )
    headers = {"User-Agent": "LucidTrendNews/1.0 (https://newspluk.com; editorial@newspluk.com)"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            pages = data.get("query", {}).get("pages", {})

        for p in pages.values():
            info = p.get("imageinfo", [{}])[0]
            img_url = info.get("url")
            width = info.get("width", 0)
            height = info.get("height", 0)
            mime = info.get("mime", "")

            if img_url and "image/" in mime and width >= 500 and width >= height:
                img_req = urllib.request.Request(img_url, headers=headers)
                with urllib.request.urlopen(img_req, timeout=12) as img_resp:
                    img_data = img_resp.read()

                with Image.open(io.BytesIO(img_data)) as im:
                    im_rgb = im.convert("RGB")
                    save_path = TEMP_DIR / f"{filename_prefix}.jpg"
                    im_rgb.save(save_path, "JPEG", quality=90)
                    print(f"[Image] Found Wikimedia press photo: {save_path}")
                    return save_path
    except Exception as e:
        print(f"[Image] Wikimedia search notice: {e}")

    return None


def generate_high_quality_flux_image(title: str, description: str = "", filename_prefix: str = "lead_thumbnail") -> Optional[Path]:
    prompt = build_grounded_flux_prompt(title=title, description=description)

    # 1. Try Cloudflare Workers AI FLUX first
    try:
        print(f"[Image] Generating grounded Cloudflare FLUX image for: '{title}'...")
        coordinator = CloudflareAccountCoordinator()
        img_b64 = coordinator.generate_image(prompt)

        if img_b64:
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]

            import base64
            img_bytes = base64.b64decode(img_b64)
            save_path = TEMP_DIR / f"{filename_prefix}.jpg"
            with open(save_path, "wb") as f:
                f.write(img_bytes)
            print(f"[Image] High-quality Cloudflare FLUX image saved to: {save_path}")
            return save_path
    except Exception as e:
        print(f"[Image] Cloudflare FLUX generation error: {e}")

    # 2. Infinite Free Fallback: Pollinations.ai FLUX (guarantees zero-cost, no quota block)
    try:
        print(f"[Image] Cloudflare busy or throttled. Engaging infinite Pollinations FLUX for: '{title}'...")
        img_b64 = generate_pollinations_image(prompt)
        if img_b64:
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]

            import base64
            img_bytes = base64.b64decode(img_b64)
            save_path = TEMP_DIR / f"{filename_prefix}.jpg"
            with open(save_path, "wb") as f:
                f.write(img_bytes)
            print(f"[Image] High-quality Pollinations FLUX image saved to: {save_path}")
            return save_path
    except Exception as e:
        print(f"[Image] Pollinations FLUX fallback error: {e}")

    return None


def acquire_editorial_thumbnail(headline: str, summary: str = "", post_id: str = "lead_thumbnail") -> Optional[Path]:
    """
    Acquires an editorial thumbnail with strict context verification:
    1. Search DuckDuckGo press images -> Verify with Gemini Vision
    2. Search Wikimedia Commons -> Verify with Gemini Vision
    3. Generate photorealistic FLUX image (Cloudflare -> Pollinations)
    """
    # 1. DuckDuckGo Image Search + Gemini Vision Guard
    saved = search_and_download_image(headline, filename_prefix=post_id)
    if saved and saved.exists():
        if verify_image_relevance(saved, topic=headline, headline=headline):
            return saved
        else:
            print(f"[Image] Discarding DuckDuckGo photo (failed vision relevance check).")
            try:
                saved.unlink()
            except Exception:
                pass

    # 2. Wikimedia Commons + Gemini Vision Guard
    wiki = search_wikimedia_image(headline, filename_prefix=post_id)
    if wiki and wiki.exists():
        if verify_image_relevance(wiki, topic=headline, headline=headline):
            return wiki
        else:
            print(f"[Image] Discarding Wikimedia photo (failed vision relevance check).")
            try:
                wiki.unlink()
            except Exception:
                pass

    # 3. Grounded FLUX AI Image (Cloudflare -> Pollinations infinite free fallback)
    return generate_high_quality_flux_image(headline, description=summary, filename_prefix=post_id)
