import subprocess, sys
from pathlib import Path


def test_icon_generation(tmp_path, monkeypatch):
    import build_icon
    build_icon.generate()
    assert Path("assets/snapstamp.ico").exists()
    assert Path("assets/snapstamp.png").exists()


def test_version_info_generation():
    import make_version_info
    make_version_info.generate()
    txt = Path("version_info.txt").read_text(encoding="utf-8")
    import version
    assert "SnapStamp" in txt
    assert "Unknown" in txt
    assert version.VERSION.split(".")[0] in txt
