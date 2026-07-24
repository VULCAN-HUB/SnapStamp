from pathlib import Path
from PIL import Image
from core.camera import get_backend
from core.camera.base import CameraBackend


def _make_samples(d: Path, n=4):
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        Image.new("RGB", (640, 480), (i * 40, 0, 0)).save(d / f"s{i}.jpg")


def test_mock_backend_is_camerabackend(tmp_path):
    _make_samples(tmp_path / "sample")
    be = get_backend({"camera": {"backend": "mock"}}, str(tmp_path / "out"))
    assert isinstance(be, CameraBackend)


def test_mock_capture_saves_file(tmp_path):
    sample = tmp_path / "sample"; _make_samples(sample)
    out = tmp_path / "out"
    be = get_backend({"camera": {"backend": "mock"}}, str(out))
    # sample_dir 주입 (테스트 편의)
    be.sample_dir = str(sample)
    assert be.connect() is True
    p = be.capture()
    assert Path(p).exists()
    assert Image.open(p).size == (640, 480)


def test_get_backend_webcam_returns_camera_backend(tmp_path):
    # "webcam"은 CameraBackend 구현체 반환(Windows=FFmpeg 우선, 아니면 cv2 WebcamBackend)
    from core.camera.base import CameraBackend
    be = get_backend({"camera": {"backend": "webcam", "device_name": "DummyCam"}}, str(tmp_path))
    assert isinstance(be, CameraBackend)


def test_get_backend_unknown_raises(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        get_backend({"camera": {"backend": "bogus"}}, str(tmp_path))
