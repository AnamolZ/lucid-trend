import io
import base64
import random
import logging
import requests
from huggingface_hub import InferenceClient

def unsplash_image(query: str, access_key: str, max_pages: int = 30) -> str:
    """
    Fetches a high-resolution, relevant tech photograph from Unsplash.
    """
    try:
        page = random.randint(1, max_pages)
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "client_id": access_key,
            "per_page": 1,
            "page": page,
            "orientation": "landscape"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        if results:
            return results[0]["urls"]["regular"]
    except Exception as e:
        logging.warning(f"[Unsplash] Image fetch failed for query '{query}': {e}")
    return None

def huggingface_image(hf_token: str, prompt: str) -> str:
    """
    Generates a visual asset using FLUX.1-schnell (high-speed free tier).
    Returns a data URI base64 PNG string.
    """
    try:
        client = InferenceClient(token=hf_token)
        image = client.text_to_image(
            prompt=prompt,
            model="black-forest-labs/FLUX.1-schnell"
        )
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode("utf-8")
        logging.info("[HuggingFace] Generated image via FLUX.1-schnell.")
        return f"data:image/png;base64,{encoded}"
    except Exception as e:
        logging.warning(f"[HuggingFace] Image generation failed: {e}")
        return None