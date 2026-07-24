from pathlib import Path
from PIL import Image
from core.compositor import cover_fit, compose


def test_cover_fit_exact_slot_size():
    src = Image.new("RGB", (1000, 500), (10, 20, 30))
    out = cover_fit(src, 200, 200)
    assert out.size == (200, 200)


def test_compose_places_four_photos(tmp_path):
    photos = []
    for i in range(4):
        p = tmp_path / f"p{i}.jpg"
        Image.new("RGB", (640, 480), (i * 50, 100, 100)).save(p)
        photos.append(str(p))
    slots = [
        {"x": 0, "y": 0, "w": 100, "h": 100},
        {"x": 100, "y": 0, "w": 100, "h": 100},
        {"x": 0, "y": 100, "w": 100, "h": 100},
        {"x": 100, "y": 100, "w": 100, "h": 100},
    ]
    out = tmp_path / "final.jpg"
    result = compose(None, slots, photos, str(out), canvas_size=(200, 200))
    assert Path(result).exists()
    im = Image.open(result)
    assert im.size == (200, 200)
    # 좌상단 슬롯(사진0, 어두움)과 우하단 슬롯(사진3, 밝음) 색이 다름
    assert im.getpixel((50, 50)) != im.getpixel((150, 150))
