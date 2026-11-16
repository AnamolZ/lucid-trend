import io
import logging
from typing import List, Dict
import requests
from PIL import Image
import instaloader

from config.settings import HTTP_HEADERS
from service.intel_extractor.db import is_post_seen

logger = logging.getLogger("IntelScraper")


def build_instaloader() -> instaloader.Instaloader:
    """
    Builds a clean, anonymous Instaloader client for public post & carousel extraction.
    Requires zero credentials, zero session files, and does not trigger checkpoints.
    """
    return instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=3,
        request_timeout=15.0,
    )


def fetch_post_images(post, max_slides: int = 3) -> List[Image.Image]:
    """Fetches high-resolution images from a public single-image or carousel (sidecar) post."""
    urls = []
    if post.typename == "GraphSidecar":
        for node in post.get_sidecar_nodes():
            if not node.is_video and node.display_url:
                urls.append(node.display_url)
    elif not post.is_video and post.url:
        urls.append(post.url)

    images = []
    for url in urls[:max_slides]:
        try:
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            images.append(img)
        except Exception as e:
            logger.warning(f"  [!] Image fetch failed for {url[:45]}...: {e}")
    return images


def scrape_profile(loader: instaloader.Instaloader, username: str, max_recent: int = 2) -> List[Dict]:
    """
    Anonymously extracts recent public posts/infographics from the given public profile.
    Completely zero login required. Never accesses restricted story endpoints.
    """
    items = []
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except Exception as e:
        print(f"  [-] Profile @{username} unavailable: {e}")
        return []

    try:
        post_iter = profile.get_posts()
        checked = 0
        for post in post_iter:
            if checked >= max_recent:
                break
            checked += 1

            if is_post_seen(post.shortcode):
                continue

            images = fetch_post_images(post)
            if not images and not post.caption:
                continue

            items.append({
                "post_id": post.shortcode,
                "profile": username,
                "type": "post",
                "caption": post.caption or "",
                "images": images,
                "date_utc": post.date_utc.isoformat() if hasattr(post, "date_utc") else "",
            })
            print(f"  [+] Discovered new public intel: @{username} [{post.shortcode}] ({len(images)} slide(s))")

    except Exception as e:
        print(f"  [!] Feed inspection error for @{username}: {e}")

    return items
