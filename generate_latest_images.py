import sys
import logging
from service.image_helper.get_image import huggingface_image
from service.tursodb.client import TursoDBService
from service.mongodb.client import MongoDBService

logging.basicConfig(level=logging.INFO)

posts = [
    {
        "id": "clean-match-v12-secure-ai-matching",
        "title": "WinPure Unveils Clean & Match v12: High-Performance Data Matching Meets Secure AI",
        "description": "Data hygiene gets a massive upgrade with WinPure's latest release, introducing breakthrough algorithmic matching speeds and enterprise-grade secure AI innovations for modern data engineers.",
        "category": ["Breaking News", "Developer Central"]
    },
    {
        "id": "verizon-cto-6g-uplink-ai-demand",
        "title": "Verizon CTO Demands 6G Uplink Breakthroughs to Fuel Next-Gen AI Workloads",
        "description": "As edge AI and distributed model inference scale exponentially, network infrastructure faces unprecedented bottlenecks. Verizon's CTO is sounding the alarm for urgent 6G uplink architectural breakthroughs.",
        "category": ["Breaking News", "Cloud & Infrastructure"]
    }
]

turso = TursoDBService()
mongo = MongoDBService()

for p in posts:
    print(f"\n==========================================")
    print(f"Generating image for: {p['id']}")
    img = huggingface_image(
        title=p["title"],
        description=p["description"],
        category=p["category"]
    )
    if img:
        print(f"Success! Generated image size: {len(img)} bytes. Prefix: {img[:35]}")
        # Update Turso
        turso_ok = turso.update_post_image(p["id"], img)
        print(f"Turso update status for {p['id']}: {turso_ok}")
        # Update MongoDB (without compression, full uncompressed quality as requested)
        mongo_ok = mongo.update_post_image(p["id"], img)
        print(f"MongoDB update status for {p['id']}: {mongo_ok}")
    else:
        print(f"Failed to generate image for {p['id']}")

print("\nAll done!")
