import os
import sys

from core.camera.base import CameraBackend
from core.camera.mock import MockCameraBackend


def _sample_dir() -> str:
    """샘플 이미지 폴더의 절대경로.

    ⚠️ 상대경로("assets/sample")를 쓰면 exe로 실행할 때 현재 작업 폴더가 달라
    샘플을 못 찾고 mock 백엔드가 조용히 '연결 안 됨' 상태가 된다(실측 확인).
    PyInstaller 번들(_MEIPASS) → 소스 트리 순으로 찾는다.
    """
    roots = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(sys._MEIPASS)
    roots.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    roots.append(os.getcwd())
    for r in roots:
        p = os.path.join(r, "assets", "sample")
        if os.path.isdir(p):
            return p
    return os.path.join(roots[0], "assets", "sample")


DEFAULT_SAMPLE_DIR = _sample_dir()


def get_backend(config: dict, save_dir: str) -> CameraBackend:
    backend = config.get("camera", {}).get("backend", "mock")
    if backend == "mock":
        return MockCameraBackend(_sample_dir(), save_dir)
    if backend == "webcam":
        import sys
        cam = config.get("camera", {})
        # 고해상도(1080p): Windows에선 FFmpeg 백엔드 우선(장치 이름 사용).
        # cv2는 이 카메라 1080p를 못 잡으므로 ffmpeg가 화질상 크게 유리.
        if sys.platform.startswith("win"):
            try:
                from core.camera.ffmpeg_cam import FFmpegCameraBackend, list_dshow_cameras
                name = cam.get("device_name", "")
                if not name:
                    cams = list_dshow_cameras()
                    idx = cam.get("device_index", 0)
                    name = cams[idx] if idx < len(cams) else (cams[0] if cams else "")
                if name:
                    w = int(cam.get("width", 1920)); h = int(cam.get("height", 1080))
                    return FFmpegCameraBackend(save_dir, name, width=w, height=h)
            except Exception:
                pass  # ffmpeg 미가용 시 cv2로 폴백
        from core.camera.webcam import WebcamBackend
        return WebcamBackend(save_dir, cam.get("device_index", 0))
    raise ValueError(f"unknown camera backend: {backend}")
