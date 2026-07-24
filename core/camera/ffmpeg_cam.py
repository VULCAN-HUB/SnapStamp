"""FFmpeg 기반 카메라 백엔드 — cv2가 못 하는 고해상도(1080p) UVC 캡처.

일부 UVC 카메라(Insta360 Ace2 Pro 등)는 cv2(DShow/MSMF)로 해상도 변경 시 멈추거나
1080p 미디어 타입을 못 잡는다. FFmpeg의 dshow는 이런 카메라의 MJPG 1080p를 제대로
협상하므로, ffmpeg를 서브프로세스로 띄워 rawvideo(rgb24) 스트림을 파이프로 읽는다.
파이프 I/O는 COM 스레드 친화성과 무관하므로 리더 스레드에서 안전하게 읽는다.
"""
import subprocess
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image
from core.camera.base import CameraBackend


def _ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def list_dshow_cameras() -> list[str]:
    """연결된 dshow 비디오 장치 '이름' 목록(ffmpeg는 인덱스가 아닌 이름을 씀)."""
    try:
        ff = _ffmpeg_exe()
    except Exception:
        return []
    try:
        p = subprocess.run([ff, "-hide_banner", "-list_devices", "true", "-f", "dshow",
                            "-i", "dummy"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=15, creationflags=_no_window())
    except Exception:
        return []
    names = []
    for line in (p.stderr or "").splitlines():
        if "(video)" in line and '"' in line:
            names.append(line.split('"')[1])
    return names


def _no_window():
    import sys
    return 0x08000000 if sys.platform.startswith("win") else 0  # CREATE_NO_WINDOW


class FFmpegCameraBackend(CameraBackend):
    def __init__(self, save_dir: str, device_name: str, width: int = 1920,
                 height: int = 1080, fps: int = 30):
        self.save_dir = save_dir
        self.device_name = device_name
        self.width, self.height, self.fps = width, height, fps
        self._proc = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._last = None
        self._want = False
        self._sup = None

    def connect(self) -> bool:
        # 논블로킹: 백그라운드 감시 스레드가 스트림을 (재)시작·유지한다. 카메라가 잠깐
        # 바쁘거나(열거 직후) 나중에 붙어도 계속 재시도 → UI를 막지 않고 알아서 연결됨.
        if not self.device_name:
            return False
        self._want = True
        if self._sup is None or not self._sup.is_alive():
            self._sup = threading.Thread(target=self._supervise, daemon=True)
            self._sup.start()
        return True

    def _supervise(self):
        import time
        fail = 0
        while self._want:
            if self._proc is None or self._proc.poll() is not None:
                # 스트림 (재)시작. ⚠️ 핵심: 프로세스가 살아있는 한 절대 죽이지 않는다.
                # 반복 kill/restart 가 UVC 드라이버를 스턱시켜 '물리 재연결 전까지 안 잡힘'을
                # 유발한다. Insta360 등은 초기화가 느리므로 첫 프레임을 넉넉히(12s) 기다리고,
                # 그 안에 못 받아도 프로세스가 살아있으면 계속 대기(느긋하게 붙게).
                if self._start_stream():
                    if self._wait_first_frame(12.0) or self.is_connected():
                        fail = 0
                        continue  # 성공했거나 프로세스는 살아있음 → 유지 감시로
                # 여기 온 것 = 시작 실패 또는 프로세스가 죽음 → 백오프 후 재시도(하드웨어 배려)
                self._kill_proc()
                fail += 1
                time.sleep(min(2.0 + fail, 6.0))
            else:
                time.sleep(0.5)  # 정상 스트림 유지 감시(죽으면 위에서 재시작)

    def _start_stream(self) -> bool:
        ff = _ffmpeg_exe()
        # 저지연 설정: 큰 rtbufsize는 프레임을 수십 초 쌓아 지연을 만든다 →
        # 작은 버퍼 + nobuffer/low_delay 로 최신 프레임만 흐르게 한다(느리면 프레임 드롭).
        cmd = [ff, "-hide_banner", "-loglevel", "error",
               "-fflags", "nobuffer", "-flags", "low_delay",
               "-f", "dshow", "-rtbufsize", "3M",
               "-video_size", f"{self.width}x{self.height}",
               "-framerate", "30", "-vcodec", "mjpeg",
               "-i", f"video={self.device_name}",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL,
                                          bufsize=self.width * self.height * 3,
                                          creationflags=_no_window())
        except Exception:
            self._proc = None
            return False
        self._running = True
        self._last = None
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        return True

    def _wait_first_frame(self, timeout: float) -> bool:
        import time
        t0 = time.time()
        while self._last is None and time.time() - t0 < timeout and self.is_connected():
            time.sleep(0.05)
        return self._last is not None

    def _reader(self):
        frame_bytes = self.width * self.height * 3
        pipe = self._proc.stdout
        while self._running and self._proc and self._proc.poll() is None:
            # 버퍼드 리더의 read(n)은 EOF가 아니면 정확히 n바이트를 채워 반환한다.
            buf = pipe.read(frame_bytes)
            if not buf or len(buf) < frame_bytes:
                return
            arr = np.frombuffer(buf, np.uint8).reshape((self.height, self.width, 3))
            with self._lock:
                self._last = Image.fromarray(arr, "RGB")

    def _kill_proc(self):
        self._running = False
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def disconnect(self) -> None:
        self._want = False   # 감시 스레드 종료
        self._kill_proc()

    def is_connected(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start_liveview(self) -> None:
        pass

    def stop_liveview(self) -> None:
        pass

    def get_frame(self):
        with self._lock:
            return self._last

    def capture(self) -> Path:
        with self._lock:
            frame = self._last
        if frame is None:
            raise RuntimeError("capture 실패: 프레임 없음")
        Path(self.save_dir).mkdir(parents=True, exist_ok=True)
        # 중간 촬영본은 무손실 PNG로 저장 → 합성 시 JPEG 압축이 한 번만 걸리게(화질↑).
        name = unicodedata.normalize("NFC", datetime.now().strftime("shot_%Y%m%d_%H%M%S_%f") + ".png")
        dst = Path(self.save_dir) / name
        frame.save(dst)  # PNG 무손실
        return dst

    @property
    def capabilities(self) -> dict:
        return {"liveview": True, "resolution": (self.width, self.height), "full_res": True}
