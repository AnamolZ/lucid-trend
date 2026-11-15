from datetime import datetime, timezone
from typing import List, Dict
import numpy as np
from rapidocr_onnxruntime import RapidOCR

from service.intel_extractor.utils import clean_text
from service.intel_extractor.db import save_post


class OCREngine:
    def __init__(self):
        self.engine = RapidOCR()

    def process_items(self, items: List[Dict]) -> List[str]:
        extracted = []
        for item in items:
            post_id = item["post_id"]
            user = item["profile"]
            images = item.get("images", [])
            caption = clean_text(item.get("caption", ""))

            slide_texts = []
            for img in images:
                result, _ = self.engine(np.array(img))
                if result:
                    lines = [line[1].strip() for line in result if line[2] >= 0.5]
                    slide_texts.append(" ".join(lines))

            image_text = clean_text(" ".join(slide_texts))

            entry = f"[Source: @{user} | ID: {post_id}]\n"
            if image_text:
                entry += f"Infographic / Image Text: {image_text}\n"
            if caption:
                entry += f"Caption: {caption}\n"

            extracted.append(entry)

            save_post(
                post_id=post_id,
                profile=user,
                published_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                text=entry,
            )

        return extracted
