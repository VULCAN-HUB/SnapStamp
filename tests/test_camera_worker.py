import time
from pathlib import Path
from PIL import Image
from PyQt5.QtGui import QImage
from core.workers.camera_worker import pil_to_qimage, CameraWorker
from core.camera.mock import MockCameraBackend


def _samples(d: Path, n=2):
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        Image.new("RGB", (320, 240), (i * 80, 10, 10)).save(d / f"s{i}.jpg")


def test_pil_to_qimage_size_and_safety(qapp):
    src = Image.new("RGB", (64, 48), (10, 20, 30))
    qi = pil_to_qimage(src)
    assert isinstance(qi, QImage)
    assert qi.width() == 64 and qi.height() == 48
    # 원본 삭제 후에도 QImage가 독립적으로 유효(.copy() 보장)
    del src
    assert qi.pixel(0, 0) != 0


def test_camera_worker_emits_frames(qapp, tmp_path):
    sample = tmp_path / "sample"; _samples(sample)
    be = MockCameraBackend(str(sample), str(tmp_path / "out"))
    be.connect()
    w = CameraWorker(be, fps=30)
    frames = []
    w.frame_ready.connect(lambda qi: frames.append(qi))
    w.start()
    time.sleep(0.3)
    w.stop()
    qapp.processEvents()
    assert len(frames) >= 1
    assert all(isinstance(f, QImage) for f in frames)


def test_camera_worker_running_false_after_error(qapp):
    class Boom:
        def get_frame(self):
            raise RuntimeError("device lost")

    w = CameraWorker(Boom(), fps=30)
    errors = []
    w.error_occurred.connect(lambda m: errors.append(m))
    w.run()  # 동기 실행: 즉시 예외→break
    assert w.running is False
    assert errors
