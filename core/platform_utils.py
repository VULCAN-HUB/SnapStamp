import ctypes
import os
import subprocess
import sys
from pathlib import Path


def is_win() -> bool:
    return sys.platform.startswith("win")


def is_mac() -> bool:
    return sys.platform == "darwin"


def platform_label() -> str:
    if is_win():
        return "Windows 10/11 64-bit"
    if is_mac():
        return "macOS"
    return "Linux"


def apply_dark_titlebar(win_id: int) -> bool:
    if not is_win():
        return False
    try:
        hwnd = ctypes.wintypes.HWND(win_id) if hasattr(ctypes, "wintypes") else win_id
        value = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (2004+ =20, 1809~ =19)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(win_id), attr, ctypes.byref(value), ctypes.sizeof(value)
            )
        return True
    except Exception:
        return False


def open_folder(path: str) -> None:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    if is_win():
        os.startfile(str(p))  # noqa: S606
    elif is_mac():
        subprocess.run(["open", str(p)], check=False)
    else:
        subprocess.run(["xdg-open", str(p)], check=False)
