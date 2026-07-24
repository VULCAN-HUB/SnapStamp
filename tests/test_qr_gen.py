from pathlib import Path
from PIL import Image
from core.qr_gen import make_qr


def test_make_qr_creates_png(tmp_path):
    out = tmp_path / "qr.png"
    result = make_qr("https://example.com/abc", str(out))
    assert Path(result).exists()
    im = Image.open(result)
    assert im.size[0] > 0 and im.size[1] > 0


def test_make_qr_empty_url_raises(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        make_qr("", str(tmp_path / "x.png"))
