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
        self._cands = None      # 입력 포맷 후보(프로브 후 캐시)
        self.last_error = ""    # 못 붙는 이유(화면에 그대로 띄운다 — 조용한 실패 금지)
        # 처리(출력) 해상도 — 부스는 1080p면 충분(템플릿 864px). 4K는 약한 PC에 과부하라
        # 캡처는 장치가 주는 대로 받되 파이프로는 최대 1080p로 낮춰 흘려 렉을 막는다.
        self._ow, self._oh = width, height

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
                        self.last_error = ""      # 붙었으면 지난 실패 사유는 지운다
                        continue  # 성공했거나 프로세스는 살아있음 → 유지 감시로
                # 여기 온 것 = 시작 실패 또는 프로세스가 죽음 → 백오프 후 재시도(하드웨어 배려)
                self._kill_proc()
                fail += 1
                # 신호가 바뀌었을 수 있다(예: 카메라 사진↔영상 모드로 HDMI 해상도/포맷 변경).
                # 몇 번 실패하면 후보 캐시를 비워 다음 시도에 '현재 신호'로 다시 프로브한다.
                if fail >= 2:
                    self._cands = None
                # ⚠️ 여기서 조용히 재시도만 하면 화면엔 "자동 연결 중"만 영원히 남는다.
                #    실제로 원인을 못 찾아 오래 헤맨 적이 있다 → 사유를 진단해 남긴다.
                if fail == 1 or fail % 5 == 0:
                    self.last_error = self._diagnose()
                time.sleep(min(2.0 + fail, 6.0))
            else:
                time.sleep(0.5)  # 정상 스트림 유지 감시(죽으면 위에서 재시작)

    def _diagnose(self) -> str:
        """왜 못 붙는지 한 줄로. 스트리밍 경로는 건드리지 않고 짧은 프로브만 따로 돌린다."""
        try:
            ff = _ffmpeg_exe()
            p = subprocess.run([ff, "-hide_banner", "-f", "dshow", "-rtbufsize", "8M",
                                "-i", f"video={self.device_name}", "-frames:v", "1",
                                "-f", "null", "-"],
                               capture_output=True, encoding="utf-8", errors="replace",
                               timeout=20, creationflags=_no_window())
            err = (p.stderr or "").lower()
        except Exception:  # noqa: BLE001
            return "카메라 연결 실패 — 케이블과 전원을 확인하세요"
        if p.returncode == 0:
            return ""                                  # 지금은 열린다(일시적 문제)
        if "could not run graph" in err or "in use" in err or "busy" in err:
            return ("다른 프로그램이 카메라를 쓰고 있습니다 — Insta360 Camera Hub·화상회의·"
                    "카메라 앱을 닫고, 그래도 안 되면 USB를 뽑았다 다시 꽂으세요")
        if "could not find" in err or "no such device" in err or "cannot find" in err:
            return "카메라를 찾을 수 없습니다 — 케이블 연결과 카메라 전원(웹캠 모드)을 확인하세요"
        if "permission" in err or "access" in err:
            return "카메라 권한이 막혀 있습니다 — Windows 설정 › 개인정보 › 카메라에서 허용하세요"
        return "카메라를 열 수 없습니다 — 다른 프로그램 종료 후 USB 재연결을 시도하세요"

    def _probe_formats(self):
        """장치가 제공하는 vcodec·pixel_format·해상도 집합(dshow -list_options)."""
        import re
        try:
            ff = _ffmpeg_exe()
            p = subprocess.run([ff, "-hide_banner", "-f", "dshow", "-list_options", "true",
                                "-i", f"video={self.device_name}"],
                               capture_output=True, encoding="utf-8", errors="replace",
                               timeout=15, creationflags=_no_window())
            txt = p.stderr or ""
            return (set(re.findall(r"vcodec=(\w+)", txt)),
                    set(re.findall(r"pixel_format=(\w+)", txt)),
                    set(re.findall(r"max s=(\d+x\d+)", txt)))
        except Exception:  # noqa: BLE001
            return set(), set(), set()

    def _candidate_inputs(self):
        """입력 포맷 후보를 우선순위대로. MJPEG(웹캠)·비압축(캡처보드) 모두 대응.

        ⚠️ 예전엔 `-vcodec mjpeg`만 강제해, MJPEG을 안 주는 캡처보드(예: Cam Link 4K,
        yuyv422만 출력)에서 스트림이 아예 안 열렸다. 이제 장치가 제공하는 포맷을 보고 시도한다.
        """
        if self._cands is not None:
            return self._cands
        vcodecs, pixfmts, sizes = self._probe_formats()
        tw, th = self.width, self.height     # 처리 '목표' 해상도 = 설정값(res_box, 기본 FHD)
        # 장치 캡처 해상도: 목표와 같은 모드가 있으면 그걸(스케일 없음), 없으면 목표 이하 최대,
        # 그것도 없으면(예: 4K만 제공) 가장 작은 것. → 목표를 4K로 두면 4K 그대로 처리(고사양용).
        if sizes:
            avail = sorted({(int(a), int(b)) for a, b in (s.split("x") for s in sizes)},
                           key=lambda wh: wh[0] * wh[1])
            if (tw, th) in avail:
                self.width, self.height = tw, th
            else:
                le = [wh for wh in avail if wh[0] <= tw and wh[1] <= th]
                self.width, self.height = (le[-1] if le else avail[0])
        # 출력(처리) 해상도: 장치가 목표보다 크면 목표로 다운스케일, 아니면 장치 그대로.
        #   기본 FHD면 4K 소스도 FHD로 낮춰 약한 PC에서 렉을 막고, 목표를 4K로 올리면 4K 처리.
        if self.width > tw or self.height > th:
            self._ow = tw
            self._oh = int(round(self.height * tw / self.width)) & ~1  # 짝수(H.264/스케일 안전)
        else:
            self._ow, self._oh = self.width, self.height
        size = ["-video_size", f"{self.width}x{self.height}"]
        opts = []
        if not vcodecs and not pixfmts:                 # 프로브 실패 → 흔한 순서로 전부 시도
            opts = [["-vcodec", "mjpeg"], ["-pixel_format", "yuyv422"],
                    ["-pixel_format", "nv12"], ["-pixel_format", "yuv420p"], []]
        else:
            if "mjpeg" in vcodecs:
                opts.append(["-vcodec", "mjpeg"])       # Insta360 등 UVC 웹캠
            for pf in ("yuyv422", "nv12", "yuv420p"):
                if pf in pixfmts:
                    opts.append(["-pixel_format", pf])  # 캡처보드·표준 웹캠(비압축)
            opts.append([])                             # 마지막 폴백: 지정 없이
        # ⚠️ -framerate는 강제하지 않는다(장치가 59.94만 줄 때 30 요구하면 열기 실패).
        self._cands = [size + o for o in opts]
        return self._cands

    def _spawn(self, input_args) -> bool:
        ff = _ffmpeg_exe()
        # 저지연: 작은 rtbufsize + nobuffer/low_delay 로 최신 프레임만(느리면 드롭).
        # ⚠️ rtbufsize를 크게 잡으면(예:64M) 리더가 잠깐 밀릴 때 수십 프레임이 쌓여
        #    화면이 소리보다 늦게 나온다(카운트다운 불일치). 몇 프레임분으로 작게 유지한다.
        # 장치가 1080p보다 크면 ffmpeg에서 다운스케일해 파이프로는 최대 1080p만 흘린다.
        vf = ["-vf", f"scale={self._ow}:{self._oh}"] if (self._ow, self._oh) != (self.width, self.height) else []
        cmd = ([ff, "-hide_banner", "-loglevel", "error",
                "-fflags", "nobuffer", "-flags", "low_delay",
                "-f", "dshow", "-rtbufsize", "8M"] + input_args +
               ["-i", f"video={self.device_name}"] + vf +
               ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL,
                                          bufsize=self._ow * self._oh * 3,
                                          creationflags=_no_window())
        except Exception:  # noqa: BLE001
            self._proc = None
            return False
        self._running = True
        self._last = None
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        return True

    def _start_stream(self) -> bool:
        # 후보 포맷을 차례로 시도 — 첫 프레임이 오는 포맷을 채택.
        # (잘못된 포맷은 ffmpeg가 곧바로 종료하므로 _wait_first_frame이 빨리 실패한다.)
        for ia in self._candidate_inputs():
            if self._spawn(ia) and self._wait_first_frame(12.0):
                return True
            self._kill_proc()
        return False

    def _wait_first_frame(self, timeout: float) -> bool:
        import time
        t0 = time.time()
        while self._last is None and time.time() - t0 < timeout and self.is_connected():
            time.sleep(0.05)
        return self._last is not None

    def _reader(self):
        ow, oh = self._ow, self._oh          # 파이프로 오는 건 '출력(다운스케일) 해상도'
        frame_bytes = ow * oh * 3
        pipe = self._proc.stdout
        while self._running and self._proc and self._proc.poll() is None:
            # 버퍼드 리더의 read(n)은 EOF가 아니면 정확히 n바이트를 채워 반환한다.
            buf = pipe.read(frame_bytes)
            if not buf or len(buf) < frame_bytes:
                return
            arr = np.frombuffer(buf, np.uint8).reshape((oh, ow, 3))
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
