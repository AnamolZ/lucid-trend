"""Static Edge Payload Baker for pre-rendering immutable CDN JSON dispatches and flat assets."""

import os
import json
import base64
import logging
from service.tursodb.client import TursoDBService

def calculate_reading_time(content: str) -> str:
    """Calculates human-readable estimated reading time based on 200 wpm standard."""
    if not content:
        return "3 min"
    words = len(content.split())
    minutes = max(1, round(words / 200))
    return f"{minutes} min"


def extract_and_save_image(post_id: str, image_data: str, target_dirs: list) -> str:
    """Extracts heavy base64 data URIs into static /images/{post_id}.jpg CDN files to keep JSON ultra-light."""
    if not image_data:
        return ""
    if not str(image_data).startswith("data:image/"):
        return image_data

    try:
        header, encoded = image_data.split(",", 1)
        ext = "jpg"
        if "png" in header:
            ext = "png"
        elif "webp" in header:
            ext = "webp"

        filename = f"{post_id}.{ext}"
        img_bytes = base64.b64decode(encoded)

        # Optional: Upload to Cloudflare R2 Object Storage for global zero-egress hosting
        try:
            from service.storage.r2_client import r2_service
            if r2_service.is_configured():
                r2_img = r2_service.upload_bytes(img_bytes, f"images/{filename}", content_type=f"image/{ext}")
                if r2_img:
                    return r2_img
        except Exception as r2_err:
            logging.warning(f"[StaticBaker] R2 upload warning for '{post_id}': {r2_err}")

        for dest in target_dirs:
            # Resolve public/images directory alongside public/api
            if dest.endswith("api") or dest.endswith("api" + os.sep):
                img_dir = os.path.abspath(os.path.join(dest, "..", "images"))
            else:
                img_dir = os.path.abspath(os.path.join(dest, "images"))

            os.makedirs(img_dir, exist_ok=True)
            img_path = os.path.join(img_dir, filename)

            # For mobile application, compress to mobile-optimized 78% quality (max-width 1080) for lean hybrid bundling (<7MB)
            if "news-pluk-application" in dest:
                try:
                    from PIL import Image
                    import io
                    with Image.open(io.BytesIO(img_bytes)) as im:
                        if im.mode in ('RGBA', 'P'):
                            im = im.convert('RGB')
                        if im.width > 1080:
                            new_height = int(im.height * (1080 / im.width))
                            im = im.resize((1080, new_height), Image.Resampling.LANCZOS)
                        im.save(img_path, 'JPEG', quality=78, optimize=True)
                        continue
                except Exception:
                    pass

            with open(img_path, "wb") as f:
                f.write(img_bytes)

        return f"/images/{filename}"
    except Exception as e:
        logging.warning(f"[StaticBaker] Error extracting base64 image for {post_id}: {e}")
        return image_data


def prune_orphaned_assets(active_ids: set, target_dirs: list) -> int:
    """Removes deleted posts' orphaned JSON, image, and audio files from static target directories."""
    if not active_ids:
        return 0

    removed_total = 0
    for dest in target_dirs:
        # 1. Prune orphaned posts/{id}.json
        posts_dir = os.path.join(dest, "posts")
        if os.path.exists(posts_dir):
            for fname in os.listdir(posts_dir):
                if fname.endswith(".json"):
                    post_id = fname[:-5]
                    if post_id not in active_ids:
                        try:
                            os.remove(os.path.join(posts_dir, fname))
                            removed_total += 1
                        except Exception:
                            pass

        # 2. Prune orphaned images/{id}.* and audio/{id}.m4a
        if dest.endswith("api") or dest.endswith("api" + os.sep):
            img_dir = os.path.abspath(os.path.join(dest, "..", "images"))
            audio_dir = os.path.abspath(os.path.join(dest, "..", "audio"))
        else:
            img_dir = os.path.abspath(os.path.join(dest, "images"))
            audio_dir = os.path.abspath(os.path.join(dest, "audio"))

        if os.path.exists(img_dir):
            for fname in os.listdir(img_dir):
                post_id = os.path.splitext(fname)[0]
                if post_id not in active_ids and not fname.startswith("avatar") and not fname.startswith("logo") and not fname.startswith("favicon"):
                    try:
                        os.remove(os.path.join(img_dir, fname))
                        removed_total += 1
                    except Exception:
                        pass

        if os.path.exists(audio_dir):
            for fname in os.listdir(audio_dir):
                if fname.endswith(".m4a"):
                    post_id = fname[:-4]
                    if post_id not in active_ids:
                        try:
                            os.remove(os.path.join(audio_dir, fname))
                            removed_total += 1
                        except Exception:
                            pass

    if removed_total > 0:
        logging.info(f"[StaticBaker] Pruned {removed_total} orphaned assets from disk.")
    return removed_total


def bake_static_payloads(target_dirs: list = None, limit: int = 50) -> dict:
    """Bakes Turso database dispatches into edge-static JSON payloads (feed.json, posts/<id>.json, search-index.json)."""
    turso = TursoDBService()
    raw_posts = turso.fetch_recent_posts_for_export(limit=limit)

    if not raw_posts:
        logging.warning("[StaticBaker] No posts returned from Turso to bake.")
        return {"total": 0, "written": 0}

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if target_dirs is None:
        target_dirs = [
            os.path.join(base_dir, "public", "api"),
            os.path.join(os.path.dirname(base_dir), "news-pluk", "public", "api"),
            os.path.join(os.path.dirname(base_dir), "news-pluk-application", "apps", "mobile", "public", "api"),
        ]
        dist_api = os.path.join(os.path.dirname(base_dir), "news-pluk", "dist", "api")
        if os.path.exists(os.path.join(os.path.dirname(base_dir), "news-pluk", "dist")):
            target_dirs.append(dist_api)

    for d in target_dirs:
        os.makedirs(d, exist_ok=True)
        os.makedirs(os.path.join(d, "posts"), exist_ok=True)

    formatted_feed_posts = []
    search_index = []

    for item in raw_posts:
        post_id = str(item.get("id"))
        title = item.get("title", "")
        desc = item.get("description", "")
        content = item.get("content", "")
        category = item.get("category", ["General"])
        raw_author = item.get("author")
        if isinstance(raw_author, dict) and raw_author.get("name") and raw_author.get("name") != "NewsPluk Editorial":
            author = raw_author
        else:
            author = {"name": "Anamol Dhakal", "role": "Backend System Developer", "avatar": "/avatar-anamol.webp"}
        audio_url = item.get("audio_url") or f"/audio/{post_id}.m4a"

        # Transform heavy base64 images into flat edge assets
        raw_image = item.get("image", "")
        static_image = extract_and_save_image(post_id, raw_image, target_dirs)
        static_thumb = extract_and_save_image(post_id, item.get("thumbnail") or raw_image, target_dirs)

        read_time = calculate_reading_time(content)

        # Full individual post document
        full_doc = {
            "id": post_id,
            "title": title,
            "slug": item.get("slug") or post_id,
            "description": desc,
            "excerpt": desc,
            "content": content,
            "image": static_image,
            "thumbnail": static_thumb,
            "audioUrl": audio_url,
            "category": category,
            "author": author,
            "source": item.get("source", "NewsPluk Editorial"),
            "readingTime": read_time,
            "published_at": item.get("published_at", ""),
            "created_at": item.get("created_at", ""),
        }

        # Lightweight feed card document
        feed_doc = {
            "id": post_id,
            "title": title,
            "slug": item.get("slug") or post_id,
            "description": desc,
            "excerpt": desc,
            "image": static_image,
            "thumbnail": static_thumb,
            "audioUrl": audio_url,
            "category": category,
            "author": author,
            "source": item.get("source", "NewsPluk Editorial"),
            "readingTime": read_time,
            "published_at": item.get("published_at", ""),
        }
        formatted_feed_posts.append(feed_doc)

        cat_str = category if isinstance(category, str) else " ".join(category)
        search_index.append({
            "id": post_id,
            "title": title,
            "description": desc,
            "category": cat_str,
        })

        # Save individual post JSON
        post_json_str = json.dumps(full_doc, indent=2, ensure_ascii=False)
        for dest in target_dirs:
            try:
                single_path = os.path.join(dest, "posts", f"{post_id}.json")
                with open(single_path, "w", encoding="utf-8") as f:
                    f.write(post_json_str)
            except Exception as e:
                logging.warning(f"[StaticBaker] Error writing single post JSON to {dest}: {e}")

    feed_payload = {
        "status": "success",
        "totalPosts": len(formatted_feed_posts),
        "posts": formatted_feed_posts,
    }
    feed_json_str = json.dumps(feed_payload, indent=2, ensure_ascii=False)
    search_json_str = json.dumps(search_index, indent=2, ensure_ascii=False)

    for dest in target_dirs:
        try:
            feed_path = os.path.join(dest, "feed.json")
            with open(feed_path, "w", encoding="utf-8") as f:
                f.write(feed_json_str)

            search_path = os.path.join(dest, "search-index.json")
            with open(search_path, "w", encoding="utf-8") as f:
                f.write(search_json_str)

            logging.info(f"[StaticBaker] Successfully baked {len(formatted_feed_posts)} articles to {dest}")
        except Exception as e:
            logging.error(f"[StaticBaker] Error writing feed.json to {dest}: {e}")

    active_ids = {str(item.get("id")) for item in raw_posts if item.get("id")}
    pruned_count = prune_orphaned_assets(active_ids, target_dirs)

    return {
        "total": len(raw_posts),
        "destinations": len(target_dirs),
        "pruned": pruned_count,
    }
