"""개발/mock용 더미 샘플 이미지 4장 생성. PII 없는 단색."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path("assets/sample")
OUT.mkdir(parents=True, exist_ok=True)
colors = [(210, 84, 0), (17, 17, 17), (60, 107, 255), (46, 204, 113)]
for i, c in enumerate(colors):
    im = Image.new("RGB", (1280, 960), c)
    d = ImageDraw.Draw(im)
    d.text((40, 40), f"SAMPLE {i + 1}", fill=(255, 255, 255))
    im.save(OUT / f"sample_{i + 1}.jpg", quality=90)
print("wrote 4 samples to", OUT)
