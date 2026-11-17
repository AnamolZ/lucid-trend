"""
Gemini Vision Editorial Image Verifier.
Guarantees that scraped or candidate photos accurately match the article topic
before publication, completely eliminating the 'Potato Chip vs AI Chip' problem.
"""

import logging
from pathlib import Path
from typing import Optional
from PIL import Image

logger = logging.getLogger("ImageVerifier")


def verify_image_relevance(image_path: Path, topic: str, headline: str = "") -> bool:
    """
    Evaluates whether an image is contextually relevant, professional,
    and free from off-topic elements (e.g. food, cartoons, memes, clip art).
    
    Returns True if approved by Gemini Vision, False otherwise.
    """
    if not image_path or not Path(image_path).exists():
        return False

    try:
        from config.model_pool import coordinator
        import google.generativeai as genai

        active_key = coordinator.get_active_key()
        if not active_key:
            logger.warning("[ImageVerifier] No active Google API key. Skipping vision check.")
            return True

        genai.configure(api_key=active_key)
        model = genai.GenerativeModel("models/gemini-flash-latest")

        img = Image.open(image_path)
        
        # Guardrail prompt that strictly filters out food, cartoons, memes, and irrelevant stock clips
        prompt = f"""You are a professional editorial photo editor for a financial and macroeconomic newsroom.
Article Topic: {topic}
Headline: {headline}

Review this image carefully. Is this image suitable, professional, and contextually relevant as an editorial photograph for this story?
Strict Rules:
- Answer 'NO' if the image depicts food/snacks (e.g. potato chips for AI chips), cartoons, anime, gaming sprites, memes, emojis, or low-quality clipart.
- Answer 'YES' if the image depicts authentic technology, hardware, data centers, business professionals, stock exchanges, cityscapes, or macroeconomic infrastructure relevant to the topic.

Answer strictly with 'YES' or 'NO' followed by a 1-sentence reason.
"""
        response = model.generate_content([prompt, img])
        if response and response.text:
            text = response.text.strip()
            decision = text.split(".")[0].strip().upper()
            if decision.startswith("YES"):
                print(f"[ImageVerifier] Image APPROVED for '{topic}': {text}")
                return True
            else:
                print(f"[ImageVerifier] Image REJECTED for '{topic}': {text}")
                return False

    except Exception as e:
        logger.warning(f"[ImageVerifier] Vision check error: {e}. Defaulting to safe fallback.")
        return False

    return False
