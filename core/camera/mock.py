import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from PIL import Image
from core.camera.base import CameraBackend


class MockCameraBackend(CameraBackend):
    def __init__(self, sample_dir: str, save_dir: str):
        self.sample_dir = sample_dir
        self.save_dir = save_dir
        self._connected = False
        self._idx = 0

    def _samples(self):
        exts = {".jpg", ".jpeg", ".png"}
        return sorted(p for p in Path(self.sample_dir).glob("*") if p.suffix.lower() in exts)

    def connect(self) -> bool:
        self._connected = len(self._samples()) > 0
        return self._connected

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def start_liveview(self) -> None:
        pass

    def stop_liveview(self) -> None:
        pass

    def get_frame(self):
        s = self._samples()
        if not s:
            return None
        return Image.open(s[self._idx % len(s)]).convert("RGB")

    def capture(self) -> Path:
        s = self._samples()
        src = s[self._idx % len(s)]
        self._idx += 1
        Path(self.save_dir).mkdir(parents=True, exist_ok=True)
        name = unicodedata.normalize("NFC", datetime.now().strftime("shot_%Y%m%d_%H%M%S_%f") + src.suffix)
        dst = Path(self.save_dir) / name
        shutil.copyfile(src, dst)
        return dst

    @property
    def capabilities(self) -> dict:
        return {"liveview": True, "resolution": (640, 480), "full_res": False}
