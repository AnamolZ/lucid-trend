import requests
import random

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