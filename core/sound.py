"""효과음 재생(Windows winsound, 비동기). 파일 없거나 타 OS면 조용히 무시."""
import os
import sys
from pathlib import Path


def _asset(name: str) -> Path:
    # PyInstaller 번들(frozen)에선 _MEIPASS 아래, 아니면 실행 폴더/작업 폴더에서 찾음
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "assets" / "sounds" / name
    return Path("assets/sounds") / name


def _play(name: str):
    if not sys.platform.startswith("win"):
        return
    path = _asset(name)
    if not path.exists():
        return
    try:
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass


def play_beep():
    _play("beep.wav")


def play_shutter():
    _play("shutter.wav")


def play_done():
    _play("done.wav")
