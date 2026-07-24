from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
from core import uploader


class NetworkWorker(QThread):
    delivery_done = pyqtSignal(str, str)   # url, mode
    delivery_failed = pyqtSignal(str)

    def __init__(self, file_path: str, serve_dir: str, timeout: float = 10.0,
                 cloud_enabled: bool = False, local_fallback: bool = True):
        super().__init__()
        self.file_path = file_path
        self.serve_dir = serve_dir
        self.timeout = timeout
        self.cloud_enabled = cloud_enabled  # 기본 False = 로컬 전달(사진이 밖으로 안 나감)
        # local_fallback=False 면 로컬 전달은 호출측(controller의 상시 서버)이 담당한다.
        self.local_fallback = local_fallback
        self.server = None  # 로컬 서버 수명은 워커가 소유(폴백을 워커가 할 때만)

    def run(self):
        # ⚠️ 기본은 로컬 전달(개인정보 보호). 클라우드(외부 업로드)는 운영자가 켰을 때만.
        if self.cloud_enabled:
            try:
                url = uploader.upload_gofile(self.file_path, timeout=self.timeout)
                self.delivery_done.emit(url, "cloud")
                return
            except uploader.UploadError as e:
                if not self.local_fallback:
                    self.delivery_failed.emit(str(e))  # 호출측이 로컬로 폴백
                    return
        try:
            self.server = uploader.LocalServer(self.serve_dir)
            base = self.server.start()
            self.delivery_done.emit(base + Path(self.file_path).name, "local")
        except Exception as e:  # noqa: BLE001
            self.delivery_failed.emit(str(e))

    def shutdown(self):
        if self.server:
            self.server.stop()
            self.server = None
