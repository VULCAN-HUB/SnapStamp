"""브랜드 아이콘 생성(Pillow). PII 없는 단순 도형."""
from pathlib import Path
from PIL import Image, ImageDraw

AMBER = (211, 84, 0)
WHITE = (255, 255, 255)


def _draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), AMBER + (255,))
    d = ImageDraw.Draw(img)
    m = size // 6
    # 카메라 바디(둥근 사각형 느낌) + 렌즈 원
    d.rounded_rectangle([m, m + size // 12, size - m, size - m], radius=size // 12,
                        outline=WHITE, width=max(2, size // 20))
    r = size // 5
    cx, cy = size // 2, size // 2 + size // 24
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=WHITE, width=max(2, size // 22))
    # 상단 뷰파인더 돌기
    d.rectangle([cx - size // 10, m - size // 40, cx + size // 10, m + size // 12], fill=WHITE)
    return img


def generate():
    Path("assets").mkdir(exist_ok=True)
    base = _draw(1024)
    base.save("assets/snapstamp.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base.save("assets/snapstamp.ico", sizes=[(s, s) for s in sizes])
    # macOS .icns (Pillow는 어느 OS에서든 저장 가능 — Mac 빌드가 바로 되도록 미리 생성)
    try:
        base.save("assets/snapstamp.icns")
    except Exception as e:  # noqa: BLE001
        print("warn: .icns 생성 실패(무시, Mac에서 iconutil로 대체 가능):", e)


if __name__ == "__main__":
    generate()
    print("wrote assets/snapstamp.png + .ico + .icns")
