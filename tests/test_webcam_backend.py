import numpy as np
import pytest
from pathlib import Path
from PIL import Image
from core.camera.webcam import bgr_to_pil, WebcamBackend
from core.camera.base import CameraBackend


class FakeCapture:
    """cv2.VideoCapture 인터페이스 흉내 (실카메라 없이 로직 검증)."""
    def __init__(self, frames):
        self._frames = frames
        self._i = 0
        self._opened = True
        self.props = {}
    def isOpened(self): return self._opened
    def read(self):
        if not self._frames:
            return False, None
        f = self._frames[self._i % len(self._frames)]
        self._i += 1
        return True, f
    def set(self, prop, val): self.props[prop] = val; return True
    def release(self): self._opened = False


def _bgr(w=32, h=24, b=200):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 0] = b  # blue channel high (BGR)
    return img


def test_bgr_to_pil_swaps_channels():
    pil = bgr_to_pil(_bgr())
    assert isinstance(pil, Image.Image) and pil.mode == "RGB"
    # BGR blue-high → RGB의 B 채널이 높아야 함
    r, g, b = pil.getpixel((0, 0))
    assert b > r and b > g


def test_webcam_backend_is_camerabackend(tmp_path):
    be = WebcamBackend(str(tmp_path), capture_factory=lambda: FakeCapture([_bgr()]))
    assert isinstance(be, CameraBackend)


def test_webcam_connect_get_capture(tmp_path):
    be = WebcamBackend(str(tmp_path), capture_factory=lambda: FakeCapture([_bgr(), _bgr(b=50)]))
    assert be.connect() is True
    assert be.is_connected() is True
    frame = be.get_frame()
    assert isinstance(frame, Image.Image)
    p = be.capture()
    assert Path(p).exists()
    be.disconnect()
    assert be.is_connected() is False


def test_webcam_connect_fail_returns_false(tmp_path):
    class Closed(FakeCapture):
        def isOpened(self): return False
    be = WebcamBackend(str(tmp_path), capture_factory=lambda: Closed([]))
    assert be.connect() is False


@pytest.mark.integration
def test_real_camera_smoke(tmp_path):
    """실카메라 있으면 1프레임 캡처. 없으면 skip(무카메라 환경 안전)."""
    import cv2, sys
    be = WebcamBackend(str(tmp_path), device_index=0)
    if not be.connect():
        pytest.skip("실카메라 없음 — 수동 QA 대상")
    try:
        frame = be.get_frame()
        assert frame is not None
        p = be.capture()
        assert Path(p).exists()
    finally:
        be.disconnect()


def test_capture_reuses_cached_frame_no_double_read(tmp_path):
    """크래시 회귀 방지: get_frame(워커) 후 capture()는 캐시된 프레임을 쓰고
    cap.read()를 다시 호출하지 않는다(동시 cap 접근 방지)."""
    class CountingCapture(FakeCapture):
        def __init__(self, frames):
            super().__init__(frames); self.reads = 0
        def read(self):
            self.reads += 1
            return super().read()
    cap = CountingCapture([_bgr(), _bgr(b=50)])
    be = WebcamBackend(str(tmp_path), capture_factory=lambda: cap)
    assert be.connect()
    be.get_frame()          # 워커가 1회 읽음 → 캐시
    reads_after_frame = cap.reads
    p = be.capture()        # 캐시 재사용 → 추가 read 없어야
    assert Path(p).exists()
    assert cap.reads == reads_after_frame, "capture가 cap.read를 다시 호출함(동시접근 위험)"
