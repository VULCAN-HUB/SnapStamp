import time
from PIL import Image
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage


def pil_to_qimage(img: Image.Image) -> QImage:
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    data = img.tobytes("raw", "RGB")
    qi = QImage(data, w, h, 3 * w, QImage.Format_RGB888)
    return qi.copy()  # 버퍼 소유권 독립(dangling 방지)


class CameraWorker(QThread):
    frame_ready = pyqtSignal(QImage)
    error_occurred = pyqtSignal(str)

    def __init__(self, backend, fps: int = 30):
        super().__init__()
        self.backend = backend
        self.interval = 1.0 / max(1, fps)
        self.running = False

    def run(self):
        self.running = True
        last = 0.0
        while self.running:
            now = time.monotonic()
            if now - last < self.interval:      # 스로틀링: 30fps 초과 방출 억제
                time.sleep(0.001)
                continue
            last = now
            try:
                frame = self.backend.get_frame()
            except Exception as e:               # noqa: BLE001
                self.running = False
                self.error_occurred.emit(str(e))
                break
            if frame is not None:
                self.frame_ready.emit(pil_to_qimage(frame))

    def stop(self):
        self.running = False
        self.wait(2000)
