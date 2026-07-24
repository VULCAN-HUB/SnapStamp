import sys
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from core.camera.base import CameraBackend


def bgr_to_pil(frame_bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb, mode="RGB")


def _default_capture_factory(device_index: int):
    def make():
        if sys.platform.startswith("win"):
            # 다른 앱들이 쓰는 Media Foundation(MSMF) 우선 → DSHOW 폴백.
            # (Insta360 등 일부 UVC는 DSHOW에서 검정/줄무늬가 나므로 MSMF가 안정적)
            for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW):
                cap = cv2.VideoCapture(device_index, backend)
                if cap.isOpened():
                    return cap
                cap.release()
            return cv2.VideoCapture(device_index)
        return cv2.VideoCapture(device_index)
    return make


class WebcamBackend(CameraBackend):
    def __init__(self, save_dir: str, device_index: int = 0, capture_factory=None):
        self.save_dir = save_dir
        self.device_index = device_index
        self._factory = capture_factory or _default_capture_factory(device_index)
        self._cap = None
        # ⚠️ cv2.VideoCapture는 스레드 안전하지 않음. 라이브뷰 워커 스레드와
        # capture() 호출이 동시에 cap.read()하면 크래시/멈춤. 락으로 직렬화하고,
        # capture()는 워커가 캐시한 최신 프레임을 재사용(cap 단일 리더 원칙).
        self._lock = threading.Lock()
        self._last = None  # 최근 get_frame 결과(PIL)

    def connect(self) -> bool:
        self._cap = self._factory()
        if not self._cap or not self._cap.isOpened():
            self._cap = None
            return False
        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 지연 억제(스펙 §7-6)
        except Exception:
            pass
        # 주의: 이 카메라(Insta360 Ace2 Pro 등 일부 UVC)는 cv2로 해상도를 바꾸면
        # read가 멈춘다(MJPG/1080p 요청 시 hang 확인). 기본 협상 해상도를 그대로 사용.
        # 고해상도가 필요하면 벤더 웹캠 드라이버/SDK 경로(v2)로.
        # 워밍업: 카메라가 안정될 때까지 유효 프레임 하나가 나올 때까지 읽어 버린다
        # (일부 UVC 카메라는 초기 프레임이 검정/깨짐 → 첫 좋은 프레임을 _last에 캐시).
        with self._lock:
            for _ in range(30):
                ok, frame = self._cap.read()
                if self._is_valid(frame):
                    self._last = bgr_to_pil(frame)
                    break
        return True

    @staticmethod
    def _is_valid(frame) -> bool:
        # None·전검정 프레임 걸러내기(간헐적 불량 프레임 방지).
        if frame is None:
            return False
        try:
            return float(frame.mean()) > 5.0
        except Exception:
            return False

    def disconnect(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def is_connected(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def start_liveview(self) -> None:
        pass  # cap 유지로 라이브뷰 상시 가능

    def stop_liveview(self) -> None:
        pass

    def get_frame(self):
        with self._lock:
            if not self._cap:
                return None
            ok, frame = self._cap.read()
            if self._is_valid(frame):
                self._last = bgr_to_pil(frame)  # 유효 프레임이면 갱신
            # 불량 프레임(검정/None)이면 마지막 좋은 프레임을 유지해 미리보기 안정화
            return self._last

    def capture(self) -> Path:
        # 워커가 캐시한 최신 프레임을 재사용(동시 cap.read 방지). 없으면 락 안에서 1회 읽음.
        with self._lock:
            frame = self._last
            if frame is None and self._cap:
                ok, f = self._cap.read()
                if ok and f is not None:
                    frame = bgr_to_pil(f)
        if frame is None:
            raise RuntimeError("capture 실패: 프레임 없음")
        Path(self.save_dir).mkdir(parents=True, exist_ok=True)
        name = unicodedata.normalize("NFC", datetime.now().strftime("shot_%Y%m%d_%H%M%S_%f") + ".png")
        dst = Path(self.save_dir) / name
        frame.save(dst)  # PNG 무손실(합성 시 JPEG 1회만)
        return dst

    @property
    def capabilities(self) -> dict:
        return {"liveview": True, "resolution": (0, 0), "full_res": False}
