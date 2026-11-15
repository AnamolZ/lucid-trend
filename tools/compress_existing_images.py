"""
Batch converts existing JPEG images to optimized 720p Mobile WebP files.
Generates ultra-light 25KB-40KB WebP companions for every article image.
"""

import os
from PIL import Image

TARGET_DIRS = [
    r"D:\lucid-trend-system\news-pluk\public\images",
    r"D:\lucid-trend-system\news-pluk\dist\images",
    r"D:\lucid-trend-system\lucid-trend\public\images",
]

def compress_images_to_webp():
    total_saved = 0
    converted_count = 0

    for directory in TARGET_DIRS:
        if not os.path.exists(directory):
            continue

        print(f"\nProcessing directory: {directory}")
        for fname in os.listdir(directory):
            if fname.lower().endswith(".jpg") or fname.lower().endswith(".jpeg") or fname.lower().endswith(".png"):
                src_path = os.path.join(directory, fname)
                base_name = os.path.splitext(fname)[0]
                webp_name = f"{base_name}.webp"
                webp_path = os.path.join(directory, webp_name)

                try:
                    orig_size = os.path.getsize(src_path)
                    with Image.open(src_path) as im:
                        if im.mode in ("RGBA", "P"):
                            im = im.convert("RGB")
                        
                        # Mobile target width: 720px (2x retina on 360-390px mobile screens)
                        if im.width > 720:
                            new_height = int(im.height * (720 / im.width))
                            im = im.resize((720, new_height), Image.Resampling.LANCZOS)

                        im.save(webp_path, "WEBP", quality=75, method=6)
                    
                    webp_size = os.path.getsize(webp_path)
                    savings_pct = (1 - (webp_size / orig_size)) * 100
                    total_saved += (orig_size - webp_size)
                    converted_count += 1
                    print(f"  ✓ {fname} ({orig_size // 1024} KB) -> {webp_name} ({webp_size // 1024} KB) [-{savings_pct:.1f}%]")
                except Exception as e:
                    print(f"  ✗ Error converting {fname}: {e}")

    print(f"\nDone! Converted {converted_count} images. Saved {total_saved / (1024 * 1024):.2f} MB of bandwidth.")

if __name__ == "__main__":
    compress_images_to_webp()

