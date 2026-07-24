from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtGui import QImage
from app.state import AppState
from core.camera import get_backend
from core.workers.camera_worker import pil_to_qimage
from core.workers.compositor_worker import CompositorWorker
from core.workers.network_worker import NetworkWorker
from core.qr_gen import make_qr

# 라이브뷰 폴링 간격(ms). cv2.VideoCapture(DirectShow)는 COM STA 특성상
# 반드시 메인 스레드에서 read해야 실프레임이 나온다(워커 스레드=검정 프레임).
# 따라서 QThread 대신 메인 스레드 QTimer로 프레임을 폴링한다.
LIVEVIEW_INTERVAL_MS = 66  # ~15fps(리더 fps와 맞춰 UI 부하 절감 — 1080p 프레임 변환 비용↑)


class AppController(QObject):
    state_changed = pyqtSignal(object)
    frame_ready = pyqtSignal(QImage)
    result_ready = pyqtSignal(str, str, str)  # final_path, qr_path, mode
    shot_captured = pyqtSignal(int, str)       # 컷 인덱스(0-based), 사진 경로
    gif_ready = pyqtSignal(str, str)           # 움짤 QR 이미지 경로, 확장자(gif/mp4)
    gif_failed = pyqtSignal(str)               # 움짤 생성 실패(자리 정리용)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: dict, save_dir: str):
        super().__init__()
        self.config = config
        self.save_dir = save_dir
        # 작업(임시) 파일은 저장 폴더를 어지럽히지 않도록 별도 폴더에 둔다.
        # 저장 폴더에는 '완성 4컷 사진'과 '완성 움짤' 두 가지만 남는다.
        import tempfile
        self.work_dir = str(Path(tempfile.gettempdir()) / "snapstamp_work")
        Path(self.work_dir).mkdir(parents=True, exist_ok=True)
        self.backend = get_backend(config, self.work_dir)
        self._session_base = None    # 이번 세션 파일 이름(사진·움짤 공통)
        self.max_shots = 4
        self.photos = []
        self.state = AppState.SETUP
        self._live_timer = None   # 메인 스레드 라이브뷰 폴링 타이머
        self.comp_worker = None
        self.net_worker = None
        self.final_path = None
        # 로컬 전달 서버는 앱 수명 동안 '하나만' 유지한다.
        # ⚠️ 세션마다 새로 띄우면 이전 손님의 QR 링크가 즉시 죽는다(실사용 치명).
        self._server = None
        self._server_base = None
        self._session_seq = 0  # 세션 식별(지난 세션의 지연 타이머가 새 세션을 건드리지 않게)
        # 움직이는 4컷용 — 최근 프레임을 축소해 계속 굴려 두고, 셔터 때 그 구간을 클립으로 쓴다.
        from collections import deque
        self._clip_buf = deque(maxlen=18)   # 약 1.2초(15fps 기준)
        self._clips = []                    # 컷별 클립
        self.gif_worker = None

    def shutdown(self):
        # QObject.__del__은 PyQt에서 안전하지 않으므로(GC 시점에 C++ 객체 소멸 가능,
        # 인터프리터 종료 시 wait() 불안정) 명시적 종료 메서드로 대체.
        try:
            self.stop_liveview()
        except Exception:  # noqa: BLE001
            pass
        try:
            # ⚠️ 반드시 백엔드를 해제한다 — 안 하면 ffmpeg 자식 프로세스가 남아
            # 앱을 닫아도 카메라를 계속 점유(다른 앱/재실행이 못 잡음)한다.
            self.backend.disconnect()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.comp_worker is not None and self.comp_worker.isRunning():
                self.comp_worker.wait(3000)
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.net_worker is not None:
                if hasattr(self.net_worker, "shutdown"):
                    self.net_worker.shutdown()
                if self.net_worker.isRunning():
                    self.net_worker.wait(12000)  # 업로드 timeout(10s)+여유
        except Exception:  # noqa: BLE001
            pass
        try:
            # ⚠️ 움짤 워커가 살아있는 채로 종료되면 QThread 파괴 크래시가 난다.
            if self.gif_worker is not None and self.gif_worker.isRunning():
                self.gif_worker.wait(15000)
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._server is not None:  # 상시 로컬 전달 서버 정리
                self._server.stop(); self._server = None
        except Exception:  # noqa: BLE001
            pass

    def reconfigure(self, config: dict, save_dir: str = None):
        """설정 화면에서 바꾼 값(카메라 백엔드·장치·슬롯·카운트다운 등)을 반영.
        라이브뷰가 돌고 있지 않을 때만 백엔드를 재생성한다(촬영 시작 직전 호출)."""
        self.config = config
        if save_dir:
            self.save_dir = save_dir
        if self._live_timer is None or not self._live_timer.isActive():
            # ⚠️ 이전 백엔드(ffmpeg 프로세스 등)를 먼저 정리해야 카메라 경합이 없다.
            try:
                self.backend.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self.backend = get_backend(config, self.work_dir)

    def reset(self):
        """진행 중 세션을 즉시 중단하고 준비 상태로(합성/전달 대기 스킵)."""
        self.stop_liveview()
        for w in (self.comp_worker, self.net_worker, self.gif_worker):
            try:
                if w is not None and w.isRunning():
                    if hasattr(w, "shutdown"):
                        w.shutdown()
                    w.wait(1500)
            except Exception:  # noqa: BLE001
                pass
        self.photos = []
        self._set(AppState.SETUP)

    def apply_settings(self, config: dict, save_dir: str = None):
        """카메라 백엔드는 건드리지 않고 설정값(카운트다운·슬롯·템플릿 등)만 갱신."""
        self.config = config
        if save_dir:
            self.save_dir = save_dir

    def begin_session(self):
        """이미 연결된(미리보기) 백엔드를 그대로 재사용해 촬영 세션 시작 — 재연결 없음."""
        self.photos = []
        self._clips = []; self._clip_buf.clear()   # 새 손님 → 이전 클립 폐기
        self._session_seq += 1  # 지난 세션의 지연 타이머가 새 세션을 건드리지 못하게
        if not self.backend.is_connected():
            self.backend.connect()
        self.start_liveview()
        self._set(AppState.IDLE)

    def discard_session(self):
        """촬영 도중 손님이 그냥 가버린 경우 — 찍힌 컷을 버리고 다음 손님 대기로 되돌린다.
        (반쯤 진행된 상태로 부스가 멈춰 다음 손님이 못 쓰는 것을 방지)"""
        for p in self.photos:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass
        self.photos = []
        self.begin_session()   # → IDLE → 대기 화면

    def _set(self, s: AppState):
        self.state = s
        self.state_changed.emit(s)

    def start_session(self):
        self.backend.connect()
        self.photos = []
        self._set(AppState.IDLE)
        self.start_liveview()

    def start_liveview(self):
        # 메인 스레드 QTimer로 프레임 폴링(DirectShow는 메인 스레드에서만 실프레임).
        if self._live_timer is None:
            self._live_timer = QTimer(self)
            self._live_timer.setInterval(LIVEVIEW_INTERVAL_MS)
            self._live_timer.timeout.connect(self._pump_frame)
        if not self._live_timer.isActive():
            self._live_timer.start()

    def _pump_frame(self):
        try:
            frame = self.backend.get_frame()
        except Exception as e:  # noqa: BLE001
            self.error_occurred.emit(str(e))
            return
        if frame is not None:
            if self.config.get("gif_enabled", True):
                try:   # 움짤용 롤링 버퍼(축소본 — 메모리 부담 최소)
                    self._clip_buf.append(frame.convert("RGB").resize((480, 270)))
                except Exception:  # noqa: BLE001
                    pass
            tone = self.config.get("tone")
            adj = self.config.get("adjust") or {}
            if (tone and tone != "원본") or any(adj.values()):
                try:
                    from core.tone import apply_look
                    frame = apply_look(frame, tone, adj)  # 미리보기도 같은 색감·보정(WYSIWYG)
                except Exception:  # noqa: BLE001
                    pass
            qi = pil_to_qimage(frame)
            if self.config.get("mirror_preview", False):
                qi = qi.mirrored(True, False)  # 좌우 반전(거울 모드) — 미리보기/촬영 일치
            self.frame_ready.emit(qi)

    def stop_liveview(self):
        if self._live_timer is not None and self._live_timer.isActive():
            self._live_timer.stop()

    def on_trigger(self):
        if self.state in (AppState.IDLE, AppState.PREVIEW) and len(self.photos) < self.max_shots:
            self._set(AppState.COUNTDOWN)
        elif self.state == AppState.PROMPT:
            self.start_session()

    def capture_current(self):
        if self.state != AppState.COUNTDOWN:
            return
        self._set(AppState.SHOOTING)
        try:
            path = self.backend.capture()
        except Exception as e:  # noqa: BLE001  — 프레임 없음 등, 크래시 대신 안전 복귀
            self.error_occurred.emit(f"촬영 실패: {e}")
            self._set(AppState.IDLE)
            return
        if self.config.get("mirror_preview", False):
            self._mirror_file(path)  # 미리보기(거울)와 결과가 일치하도록 촬영본도 좌우 반전
        if self.config.get("gif_enabled", True):
            self._clips.append(list(self._clip_buf))   # 셔터 직전 구간을 이 컷의 클립으로
        self.photos.append(str(path))
        self.shot_captured.emit(len(self.photos) - 1, str(path))
        if len(self.photos) >= self.max_shots:
            self.stop_liveview()  # 합성/업로드 중에는 라이브뷰 불필요(스레드 동시성 안정성 개선)
            self._set(AppState.COMPOSITING)
            self.run_composite()
        else:
            self._set(AppState.PREVIEW)

    @staticmethod
    def _mirror_file(path):
        try:
            from PIL import Image
            im = Image.open(path).transpose(Image.FLIP_LEFT_RIGHT)
            im.save(path)
        except Exception:  # noqa: BLE001
            pass

    def _new_session_base(self) -> str:
        """이번 세션의 파일 이름 — 사진과 움짤이 같은 이름으로 짝이 된다.
        추측 불가 토큰을 붙여 같은 망의 타인이 남의 사진을 찍어가지 못하게 한다."""
        import secrets
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"SnapStamp_{ts}_{secrets.token_urlsafe(6).replace('-', '_')}"

    def run_composite(self, out_path: str = None):
        self._session_base = self._new_session_base()
        Path(self.save_dir).mkdir(parents=True, exist_ok=True)
        out = out_path or str(Path(self.save_dir) / f"{self._session_base}.jpg")
        cs = self.config.get("canvas_size", [3960, 2280])
        self.comp_worker = CompositorWorker(
            self.config.get("template_path") or None,
            self.config.get("slots", []), self.photos, out,
            canvas_size=tuple(cs) if not self.config.get("template_path") else None,
            quality=self.config.get("jpeg_quality", 97),
            bg_color=self.config.get("bg_color", "#FFFFFF"),
            tone=self.config.get("tone"),
            brand={
                "text": self.config.get("brand_text", ""),
                "text_color": self.config.get("brand_text_color", "#222222"),
                "text_pos": self.config.get("brand_text_pos", "bottom"),
                "text_pt": self.config.get("brand_text_pt", 40),
                "text_dx": self.config.get("brand_text_dx", 0),
                "text_dy": self.config.get("brand_text_dy", 0),
                "show_date": self.config.get("brand_show_date", False),
                "logo_path": self.config.get("logo_path", ""),
                "logo_scale": self.config.get("logo_scale", 15),
                "logo_pos": self.config.get("logo_pos", "bottom-right"),
            },
            adjust=self.config.get("adjust"))
        self.comp_worker.composite_done.connect(self._on_composited)
        self.comp_worker.composite_failed.connect(self._on_worker_error)
        self.comp_worker.start()

    def _on_composited(self, final_path: str):
        self.final_path = final_path
        self._cleanup_shots()  # 합성 완료 → 중간 촬영본(PNG)은 불필요, 디스크 누적 방지
        self._set(AppState.RESULT)
        self.run_delivery(final_path)
        self.run_gif()          # 움짤은 사진을 먼저 보여준 뒤 백그라운드로

    def run_gif(self):
        """움직이는 4컷 생성 → 완성 화면에 별도 QR로 추가(사진 표시를 막지 않음)."""
        # 실제 프레임이 하나도 없으면(라이브뷰가 안 돌았던 경우) 만들지 않는다.
        if not self.config.get("gif_enabled", True) or not any(self._clips):
            return
        try:
            from core.workers.gif_worker import GifWorker
            cs = self.config.get("canvas_size", [3960, 2280])
            # 사진과 같은 이름 → 저장 폴더에 '완성 사진 + 완성 움짤' 한 쌍으로 남는다
            base = Path(self.save_dir) / (self._session_base or self._new_session_base())
            self.gif_worker = GifWorker(
                self._clips, self.config.get("slots", []), tuple(cs), base,
                bg_color=self.config.get("bg_color", "#FFFFFF"),
                tone=self.config.get("tone"), adjust=self.config.get("adjust"),
                brand={
                    "text": self.config.get("brand_text", ""),
                    "text_color": self.config.get("brand_text_color", "#222222"),
                    "text_pos": self.config.get("brand_text_pos", "bottom-center"),
                    "text_pt": self.config.get("brand_text_pt", 40),
                    "text_dx": self.config.get("brand_text_dx", 0),
                    "text_dy": self.config.get("brand_text_dy", 0),
                    "show_date": self.config.get("brand_show_date", False),
                    "logo_path": self.config.get("logo_path", ""),
                    "logo_scale": self.config.get("logo_scale", 15),
                    "logo_pos": self.config.get("logo_pos", "bottom-right"),
                },
                fmt=self.config.get("gif_format", "GIF"),
                max_w=int(self.config.get("gif_width", 720)),
                fps=int(self.config.get("gif_fps", 12)))
            self.gif_worker.gif_done.connect(self._on_gif_done)
            self.gif_worker.gif_failed.connect(self.gif_failed.emit)  # 실패해도 사진 전달엔 영향 없음
            self.gif_worker.start()
        except Exception:  # noqa: BLE001
            self.gif_failed.emit("")

    def _on_gif_done(self, path: str):
        # QR은 하나로 통합 — 받기 페이지가 사진과 함께 보여주므로 별도 QR이 필요 없다.
        try:
            self.gif_ready.emit("", Path(path).suffix.lstrip("."))
        except Exception:  # noqa: BLE001
            pass

    def _cleanup_shots(self):
        """합성에 쓰인 개별 촬영 PNG를 삭제(장시간 사용 시 디스크 무한 누적 방지).
        단, 설정에서 '개별 컷 보관'이 켜져 있으면 지우지 않는다."""
        if self.config.get("keep_cuts", False):
            # 보관 옵션이 켜져 있으면 저장 폴더가 아니라 'cuts' 하위 폴더로 옮긴다
            # (저장 폴더에는 완성 사진·움짤 두 가지만 보이도록)
            try:
                import shutil
                d = Path(self.save_dir) / "cuts"; d.mkdir(parents=True, exist_ok=True)
                for i, p in enumerate(self.photos, 1):
                    src = Path(p)
                    if src.exists():
                        shutil.move(str(src), str(d / f"{self._session_base}_{i}{src.suffix}"))
            except Exception:  # noqa: BLE001
                pass
            return
        for p in self.photos:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass

    # ── 전달(로컬 우선) ──────────────────────────────────────────────
    def _local_base(self) -> str:
        """로컬 서버를 '한 번만' 띄우고 계속 재사용 → 앞 손님 링크가 살아있다.
        포트를 고정하면 앱을 다시 켜도 이전 QR이 계속 동작한다.
        저장 경로가 바뀌면 서버가 옛 폴더를 보고 있으므로 새로 띄운다."""
        from core.uploader import LocalServer
        want = str(self.save_dir)
        Path(want).mkdir(parents=True, exist_ok=True)
        if self._server is not None and getattr(self, "_server_dir", None) != want:
            try:
                self._server.stop()
            except Exception:  # noqa: BLE001
                pass
            self._server = None
        if self._server is None:
            self._server = LocalServer(want, page_provider=self._render_share_page)
            self._server_base = self._server.start(int(self.config.get("share_port", 8765) or 0))
            self._server_dir = want
        return self._server_base

    def _render_share_page(self, name: str):
        """손님이 QR로 접속했을 때 보는 브랜딩 페이지(사진+움짤 한 곳에서 받기)."""
        from core.share_page import render_page
        d = Path(self.save_dir)
        photo = f"{name}.jpg"
        if not (d / photo).exists():
            return None
        motion = ""
        for ext in (".gif", ".mp4"):
            if (d / f"{name}{ext}").exists():
                motion = f"{name}{ext}"
                break
        return render_page(name, photo, motion,
                           expect_motion=bool(self.config.get("gif_enabled", True)),
                           cfg=self.config)

    def run_delivery(self, final_path: str):
        # 완성 사진이 곧 저장 파일이자 전달 파일 — 사본을 만들지 않아 폴더가 깔끔하다.
        share = Path(final_path)
        if self.config.get("cloud_share_enabled", False):
            self.net_worker = NetworkWorker(
                str(share), str(self.save_dir), cloud_enabled=True, local_fallback=False)
            self.net_worker.delivery_done.connect(
                lambda url, mode: self._on_delivered(str(share), url, mode))
            self.net_worker.delivery_failed.connect(lambda _: self._deliver_local(share))
            self.net_worker.start()
        else:
            self._deliver_local(share)

    def _deliver_local(self, share: Path):
        try:
            # QR은 파일이 아니라 '받기 페이지'를 가리킨다 → 사진·움짤을 한 곳에서 저장
            url = self._local_base() + "p/" + Path(share).stem
            self._on_delivered(str(share), url, "local")
        except Exception as e:  # noqa: BLE001
            self.error_occurred.emit(f"전달 실패: {e}")

    def _on_delivered(self, final_path: str, url: str, mode: str):
        qr_path = str(Path(self.work_dir) / "qr.png")
        make_qr(url, qr_path)
        self.result_ready.emit(final_path, qr_path, mode)

    def _on_worker_error(self, msg: str):
        self.error_occurred.emit(msg)
        self._set(AppState.IDLE)  # 부스 정체 방지(촬영분은 photos에 보존)
