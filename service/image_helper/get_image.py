
import requests
import random
import io
import base64
from huggingface_hub import InferenceClient

def unsplash_image(query, access_key, max_pages=50):
    page = random.randint(1, max_pages)
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "client_id": access_key,
        "per_page": 1,
        "page": page
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    if not results:
        return None
    return results[0]["urls"]["regular"]

def huggingface_image(HUGGING_FACE_TOKEN, prompt):

    client = InferenceClient(token=HUGGING_FACE_TOKEN)

    image = client.text_to_image(
        prompt=prompt,
        model="black-forest-labs/FLUX.1-dev"
    )

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)

    encoded = base64.b64encode(buf.read()).decode("utf-8")
    print("Generated Via Hugging Face")
    return f"data:image/png;base64,{encoded}"

if __name__ == "__main__":
    import os
    HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKEN")
    huggingface_image(HUGGING_FACE_TOKEN, "A sleek, futuristic desktop interface with an AI assistant icon, holographic elements, and a glowing digital dashboard, representing seamless Copilot integration, vibrant colors, clean modern design, 16:9 thumbnail format")