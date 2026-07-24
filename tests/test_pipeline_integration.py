from pathlib import Path
from PIL import Image
from core.camera import get_backend
from core.compositor import compose
from core.qr_gen import make_qr
from core import uploader


def _samples(d: Path, n=4):
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        Image.new("RGB", (640, 480), (i * 40, 60, 90)).save(d / f"s{i}.jpg")


def test_capture_compose_qr_deliver(tmp_path, monkeypatch):
    sample = tmp_path / "sample"; _samples(sample)
    out = tmp_path / "out"

    be = get_backend({"camera": {"backend": "mock"}}, str(out))
    be.sample_dir = str(sample)
    assert be.connect()
    photos = [str(be.capture()) for _ in range(4)]
    assert len(photos) == 4

    slots = [{"x": 0, "y": 0, "w": 100, "h": 100},
             {"x": 100, "y": 0, "w": 100, "h": 100},
             {"x": 0, "y": 100, "w": 100, "h": 100},
             {"x": 100, "y": 100, "w": 100, "h": 100}]
    final = compose(None, slots, photos, str(out / "final.jpg"), canvas_size=(200, 200))
    assert Path(final).exists()

    monkeypatch.setattr(uploader, "upload_gofile",
                        lambda p, timeout=10.0: "https://gofile.io/d/TEST")
    url, mode = uploader.deliver(str(final), str(out))
    assert mode == "gofile"

    qr = make_qr(url, str(out / "qr.png"))
    assert Path(qr).exists()
