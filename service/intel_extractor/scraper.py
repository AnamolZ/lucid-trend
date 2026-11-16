import io
from typing import List, Dict
import requests
from PIL import Image
import instaloader

from config.settings import (
    HTTP_HEADERS,
    INSTAGRAM_USER,
    INSTAGRAM_SESSIONID,
)
from service.intel_extractor.db import is_post_seen


def build_instaloader() -> instaloader.Instaloader:
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=3,
        request_timeout=15.0,
    )

    if INSTAGRAM_SESSIONID:
        try:
            user_id = INSTAGRAM_SESSIONID.split("%3A")[0]
            loader.context.update_cookies({
                "sessionid": INSTAGRAM_SESSIONID,
                "ds_user_id": user_id,
            })
            loader.context.username = INSTAGRAM_USER
        except Exception:
            pass

    if INSTAGRAM_USER:
        try:
            loader.load_session_from_file(INSTAGRAM_USER)
            print(f"[Auth] Loaded session for @{INSTAGRAM_USER}")
        except Exception:
            pass

    return loader


def fetch_post_images(post, max_slides: int = 3) -> List[Image.Image]:
    urls = []
    if post.typename == "GraphSidecar":
        for node in post.get_sidecar_nodes():
            if not node.is_video:
                urls.append(node.display_url)
    elif not post.is_video:
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
            print(f"  [!] Image fetch failed: {e}")
    return images


def scrape_profile(loader: instaloader.Instaloader, username: str) -> List[Dict]:
    items = []
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
    except Exception as e:
        print(f"  [-] Profile @{username} unavailable: {e}")
        return []

    # Check stories if authenticated
    if loader.context.is_logged_in:
        try:
            for story in loader.get_stories(userids=[profile.userid]):
                for item in story.get_items():
                    story_id = f"story_{item.mediaid}"
                    if not item.is_video and not is_post_seen(story_id):
                        try:
                            resp = requests.get(item.url, headers=HTTP_HEADERS, timeout=15)
                            resp.raise_for_status()
                            img = Image.open(io.BytesIO(resp.content))
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            items.append({
                                "post_id": story_id,
                                "profile": username,
                                "type": "story",
                                "caption": "",
                                "images": [img],
                            })
                        except Exception as e:
                            print(f"  [!] Story download error: {e}")
        except instaloader.exceptions.LoginRequiredException:
            print(f"  [!] Instagram session expired or requires re-authentication. Skipping stories for @{username}.")
        except Exception as e:
            print(f"  [!] Stories notice for @{username}: {e}")

    # Check feed posts with fallback
    try:
        latest_post = next(profile.get_posts(), None)
    except instaloader.exceptions.LoginRequiredException:
        print(f"  [!] Login required for @{username} feed. Switching to public loader...")
        anon_loader = instaloader.Instaloader(download_pictures=False, download_videos=False, save_metadata=False)
        try:
            anon_profile = instaloader.Profile.from_username(anon_loader.context, username)
            latest_post = next(anon_profile.get_posts(), None)
        except Exception as anon_err:
            print(f"  [-] Public fetch failed for @{username}: {anon_err}")
            latest_post = None
    except Exception:
        anon_loader = instaloader.Instaloader(download_pictures=False, download_videos=False, save_metadata=False)
        try:
            anon_profile = instaloader.Profile.from_username(anon_loader.context, username)
            latest_post = next(anon_profile.get_posts(), None)
        except Exception:
            latest_post = None

    if latest_post and not is_post_seen(latest_post.shortcode):
        images = fetch_post_images(latest_post)
        items.append({
            "post_id": latest_post.shortcode,
            "profile": username,
            "type": "post",
            "caption": latest_post.caption or "",
            "images": images,
        })

    return items
