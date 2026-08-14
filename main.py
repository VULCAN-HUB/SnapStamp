import sys
import json
from pathlib import Path
from PyQt5.QtCore import Qt, QTimer, QThread, QObject, QEvent, pyqtSignal
from PyQt5.QtWidgets import QApplication, QStackedWidget, QMessageBox, QShortcut
from PyQt5.QtGui import QKeySequence
from config import load_config
from app.controller import AppController
from app.state import AppState
from ui.setup_window import SetupWindow
from ui.shoot_window import ShootWindow
from ui.result_window import ResultWindow
from ui.audience_window import AudienceWindow
from ui.attract_window import AttractWindow
from core.platform_utils import apply_dark_titlebar
from ui.theme import apply_app_style


class _CamScan(QThread):
    """카메라 열거를 백그라운드에서 실행(UI 프리징 방지)."""
    found = pyqtSignal(list)

    def run(self):
        names = []
        try:
            from core.camera.ffmpeg_cam import list_dshow_cameras
            names = list_dshow_cameras() or []
        except Exception:
            names = []
        self.found.emit(names)


class KeyRouter(QObject):
    """앱 전역 키 라우터 — 포커스·활성 창과 무관하게 키를 받아 handler 로 넘긴다.

    ⚠️ 이게 없으면 보조 모니터(손님) 창이 전체화면으로 뜨는 순간 그 창이 활성 창이 되어
    메인 창의 keyPressEvent·QShortcut(WindowShortcut)이 전부 죽는다(실측:
    activeWindow=AudienceWindow, focusWidget=손님 창 내부 위젯). 손님이 트리거를 눌러도
    촬영이 시작되지 않던 원인.

    handler(key) 가 True 를 돌려주면 그 키를 삼킨다(중복 처리 방지).
    """

    def __init__(self, handler):
        super().__init__()
        self._handler = handler

    def eventFilter(self, obj, ev):
        if (ev.type() == QEvent.KeyPress and not ev.isAutoRepeat()
                and QApplication.activeModalWidget() is None   # 종료 확인 등 대화상자 우선
                and self._handler(ev.key())):
            return True
        return super().eventFilter(obj, ev)


def _app_dir():
    # 실행 파일(frozen) 또는 스크립트가 있는 폴더 — 설정을 여기 저장(영구 보존)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _config_path():
    return str(_app_dir() / "config.json")


def _save_config(cfg):
    try:
        Path(_config_path()).write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def main():
    # High-DPI 필수 — 모니터 배율(125%/150%)에서 전체화면 하단 잘림 방지(레이아웃이 논리픽셀에 맞춰짐).
    # ⚠️ QApplication 생성 전에 설정해야 적용됨.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("SnapStamp")      # 작업표시줄/Alt+Tab 식별용
    apply_app_style(app)
    cfg = load_config(_config_path())
    save_dir = cfg.get("save_path", "results")
    controller = AppController(cfg, save_dir)
    app.aboutToQuit.connect(controller.shutdown)

    stack = QStackedWidget()
    setup = SetupWindow(cfg)
    attract = AttractWindow()   # 손님용 대기 화면(세션 중 유휴 상태의 얼굴)
    shoot = ShootWindow(controller)
    result = ResultWindow()
    for w in (setup, attract, shoot, result):
        stack.addWidget(w)

    # 보조 모니터용 관객 창 — 라이브뷰/카운트다운을 항상 미러링
    audience = AudienceWindow()

    def switch_to(widget):
        # ⚠️ 예전엔 QGraphicsOpacityEffect 페이드(280ms)를 넣었는데, 전체화면 위젯을
        #    매 프레임 오프스크린으로 재합성해 화면 전환마다 눈에 띄게 버벅였다.
        #    즉시 전환이 부스에선 더 또렷하고 빠르다.
        stack.setCurrentWidget(widget)
        widget.setFocus()  # 스페이스바 입력(시작/더블탭)을 현재 화면이 받도록
        # ⚠️ 손님 창은 **여기 한 곳에서만** 따라간다. 전환 지점마다 따로 부르면 반드시
        #    빠뜨리는 곳이 생겨 두 모니터가 어긋난다(실제로 go_ready·방치복귀에서 났다).
        page = {setup: audience.show_ready, attract: audience.show_ready,
                shoot: audience.show_live, result: audience.show_result_page}.get(widget)
        if page:
            page()

    # 라이브 프레임은 촬영화면·설정 미리보기·관객 창 모두에 전달(관객 창은 항상 미러링)
    controller.frame_ready.connect(shoot.on_frame)
    controller.frame_ready.connect(setup.show_preview_frame)
    controller.frame_ready.connect(audience.on_frame)
    controller.frame_ready.connect(audience.attract.on_frame)   # 손님 준비 화면도 라이브
    controller.frame_ready.connect(attract.on_frame)
    controller.shot_captured.connect(shoot.set_cut_thumbnail)
    controller.shot_captured.connect(audience.set_cut_thumbnail)   # 손님 화면도 컷이 쌓임

    def _wifi_qr_path():
        # 설정된 손님 WiFi가 있으면 완성 화면에 함께 띄울 WiFi 접속 QR 생성
        gw = controller.config.get("guest_wifi", {}) or {}
        if gw.get("mode", "off") in ("current", "hotspot") and gw.get("ssid"):
            try:
                from core.qr_gen import make_wifi_qr
                p = str(Path(controller.work_dir) / "wifi_qr.png")
                make_wifi_qr(gw["ssid"], gw.get("password", ""), p)
                return p
            except Exception:  # noqa: BLE001
                return None
        return None

    controller.gif_ready.connect(result.show_motion_qr)   # 움짤 준비되면 QR 추가
    controller.gif_failed.connect(result.motion_failed)   # 실패하면 자리 정리
    controller.gif_ready.connect(audience.result.show_motion_qr)
    controller.gif_failed.connect(audience.result.motion_failed)

    def _on_result(fp, qr, mode):
        # 운영자 화면과 손님 화면에 같은 완성 결과(사진 + QR)를 띄운다.
        rev_on = controller.config.get("reveal_enabled", True)
        rev_sec = controller.config.get("reveal_sec", 2)
        wifi = _wifi_qr_path()
        motion = controller.config.get("gif_enabled", True)
        for w in (result, audience.result):
            w.set_reveal_enabled(rev_on, rev_sec)
            w.show_result(fp, qr, mode, wifi, motion)
        switch_to(result)
    controller.result_ready.connect(_on_result)

    def test_camera():
        # 설정 화면에서 카메라 미리보기: 선택한 백엔드/장치로 라이브뷰 시작
        controller.stop_liveview()
        new_cfg = setup.collect()
        controller.reconfigure(new_cfg, new_cfg.get("save_path", save_dir))
        controller.backend.connect()
        controller.start_liveview()
    setup.test_camera_requested.connect(test_camera)

    scans = []  # 스캔 스레드 참조 보관(GC 방지)

    def scan_cameras(on_done):
        setup.cam_status.setText("● 검색 중…")
        w = _CamScan()
        w.found.connect(on_done)
        w.finished.connect(lambda: (scans.remove(w) if w in scans else None))
        scans.append(w)
        w.start()

    def search_cameras():
        controller.stop_liveview()
        scan_cameras(setup.set_camera_list)
    setup.camera_search_requested.connect(search_cameras)

    from core import sound

    def _snd(fn):
        # 효과음 on/off 설정 반영
        if controller.config.get("sound_enabled", True):
            fn()

    def run_countdown(sec):
        # 3→2→1 (매초 비프) 후 셔터(플래시+셔터음)와 함께 촬영. 플래시·소리는 설정으로 on/off.
        flash_on = controller.config.get("flash_enabled", True)

        def tick(n):
            if n <= 0:
                shoot.show_countdown(0); audience.show_countdown(0)
                if flash_on:
                    shoot.flash(); audience.flash()
                _snd(sound.play_shutter)
                controller.capture_current()
                return
            shoot.show_countdown(n); audience.show_countdown(n)
            _snd(sound.play_beep)
            QTimer.singleShot(1000, lambda: tick(n - 1))
        tick(sec)

    # 준비 화면 방치 감지 타이머(운영자 설정: ready_timeout_sec) + 남은시간 예고 틱
    ready_timer = QTimer(); ready_timer.setSingleShot(True)
    ready_tick = QTimer(); ready_tick.setInterval(1000)
    ready_left = {"n": 0, "warn_at": 0, "msg": "", "fn": None}

    def _stop_ready():
        ready_timer.stop(); ready_tick.stop()
        ready_left["fn"] = None
        shoot.set_warning("")

    def _arm_idle(seconds, fn, msg):
        """방치 감지 타이머 무장 — 절반(내림) 남은 시점부터 예고 문구 표시."""
        _stop_ready()
        seconds = int(seconds or 0)
        if seconds <= 0:
            return
        ready_left.update(n=seconds, warn_at=seconds // 2, msg=msg, fn=fn)
        ready_timer.start(seconds * 1000)
        ready_tick.start()

    def on_state(s):
        _stop_ready()  # 상태가 바뀌면(촬영 시작·복귀 등) 방치 타이머·예고 해제
        if s == AppState.COUNTDOWN:
            switch_to(shoot)      # 대기 화면에서 트리거 → 촬영 화면(손님 창도 함께 따라옴)
            audience.hide_design(); shoot.hide_design()   # 찍는 동안은 라이브뷰가 화면을 다 쓴다
            run_countdown(controller.config.get("countdown_sec", 3))
        elif s == AppState.PREVIEW:
            shoot.set_shot_count(len(controller.photos))
            shoot.set_hint("버튼을 눌러 다음 컷을 촬영하세요")
            audience.set_hint(f"{len(controller.photos)} / 4 컷 · 다음 컷을 준비하세요 📸")
            switch_to(shoot)
            # 촬영 도중 손님이 가버린 경우 대비 — 컷마다 방치 타이머 재무장
            _arm_idle(controller.config.get("abandon_timeout_sec", 60),
                      _abandon_session, "{n}초 뒤에 처음으로 돌아갑니다 · 촬영한 컷은 취소됩니다")
        elif s == AppState.IDLE:
            # 유휴(=다음 손님 준비) → 시네마틱 대기 화면
            shoot.set_shot_count(0)
            shoot.set_hint("버튼을 눌러 촬영을 시작하세요")
            audience.set_hint("곧 촬영을 시작합니다 📸")
            audience.set_shot_count(0)      # 다음 손님 → 컷 비우고 준비 화면으로
            switch_to(attract)
            refresh_design()                # 대기 화면 문구 자리에 지금 디자인
        elif s == AppState.COMPOSITING:
            shoot.set_hint("사진을 만들고 있어요…")
            # ⚠️ 마지막 컷도 셔터 플래시(130ms)가 '항상' 보이도록 합성 대기 화면을 살짝 뒤로.
            # (즉시 띄우면 busy 오버레이가 플래시를 덮어 4컷째만 안 깜박이는 현상)
            QTimer.singleShot(190, shoot.show_busy)
            audience.set_hint("✨ 사진을 만들고 있어요…")
        elif s == AppState.RESULT:
            _snd(sound.play_done)
            # 완성 후 자동 복귀(설정 초>0) → 그 시간 뒤 다음 손님 대기 화면으로
            ar = controller.config.get("auto_return_sec", 0)
            if ar and ar > 0:
                # ⚠️ 세션 번호를 함께 확인 — 앞 손님의 타이머가 다음 손님 세션을 끊지 않게.
                seq = controller._session_seq
                QTimer.singleShot(int(ar) * 1000, lambda: (
                    ready_for_next()
                    if (controller.state == AppState.RESULT
                        and controller._session_seq == seq) else None))
            audience.set_hint("완성! QR로 사진을 받아가세요 🎉")
    controller.state_changed.connect(on_state)

    def to_setup():
        # 운영자 복귀: 세션 종료 → 설정 화면(카메라 미리보기 재개)
        controller.reset()
        switch_to(setup)
        test_camera()
    shoot.home_requested.connect(to_setup)        # 촬영 화면 ↺(운영자)
    attract.setup_requested.connect(to_setup)     # 대기 화면 ⚙/Esc(운영자)

    def ready_for_next():
        # 다음 손님 준비: 세션은 유지하고 촬영분만 초기화 → 대기 화면으로(IDLE)
        controller.begin_session()
    result.home_requested.connect(ready_for_next)  # 완성 → 다음 손님(대기 화면)

    def _ready_timeout():
        fn = ready_left.get("fn")
        _stop_ready()
        if fn:
            fn()
    ready_timer.timeout.connect(_ready_timeout)

    def _ready_tick():
        # 설정 시간의 '절반(내림)'이 남은 시점부터 남은 초를 예고 → 갑자기 튀지 않게
        ready_left["n"] -= 1
        n = ready_left["n"]
        if n <= 0:
            return
        if n <= ready_left["warn_at"]:
            msg = ready_left["msg"].format(n=n)
            shoot.set_warning(msg)
            audience.set_hint(msg)
    ready_tick.timeout.connect(_ready_tick)

    def _back_to_attract():
        # 준비 화면 방치 → 대기 화면으로(찍은 컷 없음). 손님 창은 switch_to 가 함께 되돌린다.
        if controller.state == AppState.IDLE and stack.currentWidget() is shoot:
            switch_to(attract)
            audience.set_hint("곧 촬영을 시작합니다 📸")

    def _abandon_session():
        # 촬영 도중 방치 → 찍힌 컷 폐기하고 다음 손님 대기로
        if controller.state == AppState.PREVIEW:
            controller.discard_session()

    def go_ready():
        """대기 화면에서 트리거 1회 → 촬영(준비) 화면만 표시. 카운트다운은 아직 시작 안 함.
        손님이 전체화면으로 자기 모습을 보고 자세를 잡은 뒤, 한 번 더 눌러야 촬영이 시작된다."""
        if controller.state != AppState.IDLE:
            return
        switch_to(shoot)
        shoot.set_hint("준비되면 버튼을 한 번 더 눌러 촬영을 시작하세요")
        audience.set_hint("준비되면 버튼을 눌러주세요 📸")
        refresh_design()          # 손님 화면에 지금 디자인 + 고르기 안내
        _arm_idle(controller.config.get("ready_timeout_sec", 30),
                  _back_to_attract, "{n}초 뒤에 처음으로 돌아갑니다")

    def start():
        # 미리보기로 이미 연결된 카메라를 그대로 재사용 → 재연결 없이 즉시 대기 화면으로.
        new_cfg = setup.collect()
        _save_config(new_cfg)  # 설정 영구 저장(다음 실행 시 자동 복원)
        controller.apply_settings(new_cfg, new_cfg.get("save_path", save_dir))
        trigger = new_cfg.get("trigger_key", "Space")
        trig["key"] = trigger           # 앱 전역 라우터가 볼 현재 트리거 키
        result.set_trigger(trigger)     # 완성 화면 재시작 트리거
        attract.set_trigger(trigger)    # 대기 화면 시작 트리거
        audience.set_trigger(trigger)   # 손님 화면 시작·재시작 안내 문구
        controller.begin_session()      # IDLE → on_state 가 대기 화면으로 전환
    setup.start_requested.connect(start)

    # ── 앱 전역 키 라우터 — 손님 창이 활성 창이어도 트리거가 살아 있게 ──
    trig = {"key": cfg.get("trigger_key", "Space")}

    def on_global_key(k):
        """현재 화면에 맞춰 트리거를 배분. 설정 화면에선 가로채지 않는다(키 입력 방해 금지)."""
        cur = stack.currentWidget()
        name = QKeySequence(k).toString()
        if name and name == QKeySequence(trig["key"]).toString():
            if cur is attract:
                go_ready(); return True          # 대기 → 촬영 준비 화면
            if cur is shoot:
                controller.on_trigger(); return True   # 준비 → 카운트다운 → 다음 컷
            if cur is result:
                result.trigger_pressed(); return True  # 두 번 빠르게 → 다음 손님
            return False
        if k == Qt.Key_Escape and cur is attract:
            to_setup(); return True              # 운영자: 대기 화면에서 설정 복귀
        # 손님이 촬영 직전에 디자인을 고른다 — 준비 화면에서만, 아직 한 컷도 안 찍었을 때만.
        # (컷을 찍은 뒤 바꾸면 앞 컷과 비율이 달라져 합성이 어긋난다.)
        if (k in (Qt.Key_Left, Qt.Key_Right) and cur in (attract, shoot)
                and controller.state == AppState.IDLE and not controller.photos):
            return pick_design(-1 if k == Qt.Key_Left else 1)
        return False
    key_router = KeyRouter(on_global_key)
    app.installEventFilter(key_router)

    def refresh_design(choosable=None):
        """지금 디자인을 두 화면에 보여준다. **고르기 안내(◀▶)는 2개 이상일 때만.**

        ⚠️ 손님 화면에는 **운영자가 넣은 레이아웃만** 보인다. 예시(빌트인)가 활성이면
        내 레이아웃으로 옮기고, 그것도 없으면 디자인 칸 자체를 숨긴다 —
        손님이 부스와 상관없는 예시 이름을 보면 안 된다.
        """
        names = [u["name"] for u in setup.user_layouts]
        e = setup._find_entry(getattr(setup, "_active_layout", None))
        if (e is None or e.get("builtin")) and names:
            setup._step_user_layout(1)                 # 예시 → 내 레이아웃으로
            e = setup._find_entry(setup._active_layout)
        if e is None or e.get("builtin"):
            attract.set_design(""); audience.attract.set_design("")
            audience.hide_design(); shoot.hide_design()
            return
        if choosable is None:
            choosable = len(names) >= 2
        pm = setup.layout_preview_pixmap(e)
        name = (e or {}).get("name", "")
        # 고르는 자리는 **대기 화면**이다(좌측 문구 자리). 촬영 화면은 라이브뷰가 주인공.
        attract.set_design(name, pm, choosable)
        audience.attract.set_design(name, pm, choosable)
        audience.hide_design(); shoot.hide_design()

    def pick_design(d):
        """손님이 방향키로 디자인 변경 → 촬영 설정(슬롯·캔버스·템플릿)을 즉시 반영."""
        if not setup._step_user_layout(d):
            return False
        cfg = setup.collect()
        controller.apply_settings(cfg, cfg.get("save_path", save_dir))
        _save_config(cfg)
        refresh_design(True)
        shoot.set_hint("‘%s’ · 준비되면 버튼을 눌러 촬영 시작" % cfg.get("active_layout", ""))
        return True

    def auto_connect():
        # 시작 시 카메라 자동 연결. ⚠️ 저장된 카메라가 있으면 '열거(장치 이중 오픈)'를
        # 건너뛰고 바로 연결한다 — launch 때 list_devices+connect 로 장치를 두 번 열면
        # 경합해 UVC가 스턱될 수 있어(물리 재연결 전까지 안 잡힘) 이를 피한다.
        cam = cfg.get("camera", {})
        # mock(샘플 이미지) 백엔드는 장치 열거가 필요 없다. ⚠️ 여기서 걸러내지 않으면
        #    아래 감지 경로가 실제 웹캠을 찾아 backend를 'webcam'으로 덮어써 버려
        #    mock을 골라도 절대 동작하지 않는다(그 과정에서 장치를 두 번 열어 스턱까지 유발).
        if cam.get("backend") == "mock":
            setup.backend_box.setCurrentText("mock")
            setup.set_camera_list([])
            setup.cam_status.setText("● 샘플 이미지")   # '카메라 없음'으로 보이지 않게
            controller.backend.connect()
            controller.start_liveview()
            return
        def pick_available(cams):
            # 열거된 장치 중 하나로 전환·연결(저장 장치가 사라졌을 때 자동 복구)
            setup.set_camera_list(cams)
            if cams:
                setup.backend_box.setCurrentText("webcam")
                test_camera()

        if cam.get("backend") == "webcam" and cam.get("device_name"):
            setup.backend_box.setCurrentText("webcam")
            test_camera()   # 저장 장치로 바로 연결 시도(빠른 경로, 열거 없음)

            def _verify_or_rescan():
                # 저장 장치가 없으면(캡처보드로 교체 등) 프레임이 끝내 안 온다 →
                # 그때만 열거해서 실제 연결된 장치로 전환한다(정상·느린 장치는 건드리지 않음).
                if controller.backend.get_frame() is not None:
                    return
                scan_cameras(pick_available)
            QTimer.singleShot(13000, _verify_or_rescan)  # Insta360 등 느린 첫프레임(≤12s) 배려
            return
        # 저장된 카메라가 없을 때만 백그라운드 감지(UI 안 멈춤)
        scan_cameras(pick_available)

    # 카메라 실패 사유 감시 — 백엔드가 조용히 재시도만 하지 않도록 화면에 띄운다
    def _watch_camera_error():
        err = getattr(controller.backend, "last_error", "")
        if not err:
            return
        setup.set_camera_error(err)
        # 촬영/손님 화면에도 같은 사유를 띄운다(운영자가 설정 화면에 없을 수도 있다)
        shoot.set_warning("⚠ " + err)
        audience.set_hint("잠시만요 — 카메라를 준비하고 있어요")
    cam_err_timer = QTimer(); cam_err_timer.setInterval(3000)
    cam_err_timer.timeout.connect(_watch_camera_error)
    cam_err_timer.start()

    def safe_quit():
        # 안전 종료: 확인 후 종료(aboutToQuit → controller.shutdown 로 카메라/스레드 정리)
        box = QMessageBox(stack)
        box.setWindowTitle("종료")
        box.setText(
            "SnapStamp를 종료할까요?\n\n"
            "⚠ 종료하면 손님에게 나눠준 사진·움짤 QR 링크가 즉시 끊깁니다.\n"
            "아직 받아가지 않은 손님이 없는지 확인해 주세요.\n"
            "(사진 파일은 저장 폴더에 그대로 남습니다)")
        box.setIcon(QMessageBox.Question)
        yes = box.addButton("종료", QMessageBox.AcceptRole)
        box.addButton("취소", QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() is yes:
            audience.close()
            app.quit()
    setup.quit_requested.connect(safe_quit)
    def _app_shortcut(seq, fn):
        # ⚠️ 기본 컨텍스트(WindowShortcut)는 손님 창이 활성 창일 때 죽는다 → 앱 범위로.
        sc = QShortcut(QKeySequence(seq), stack, activated=fn)
        sc.setContext(Qt.ApplicationShortcut)
        return sc

    _app_shortcut("Ctrl+Q", safe_quit)  # 어디서든 안전 종료

    def toggle_main_fullscreen():
        # F11: 메인 창 전체화면 ↔ 창모드(창모드에서 자유 이동/크기조절 가능)
        if stack.isFullScreen():
            stack.showNormal(); stack.resize(1280, 800)
        else:
            stack.showFullScreen()
    _app_shortcut("F11", toggle_main_fullscreen)

    def toggle_audience():
        # F2: 관객(보조 모니터) 창 열기/닫기
        if audience.isVisible():
            audience.hide()
        else:
            audience.show(); audience.raise_()
    _app_shortcut("F2", toggle_audience)

    stack.setWindowTitle("SnapStamp — Event Photobooth")

    def _to_screen(win, screen):
        """창을 지정한 모니터로 옮겨 전체화면. 전체화면 상태에선 move가 안 먹으므로 먼저 푼다."""
        if win.isFullScreen():
            win.showNormal()
        g = screen.geometry()
        win.move(g.x(), g.y())
        win.showFullScreen()

    swapped = {"on": False}

    def place_windows():
        """운영자 창 = 주 디스플레이, 손님 창 = 나머지 모니터. **명시 배치**.

        ⚠️ 그냥 `showFullScreen()` 하면 그 창이 놓여 있던 화면에서 전체화면이 되고,
        손님 창을 `screens()[1]` 로 고정하면 뒤집힌다 — `screens()` 순서는 주 디스플레이
        순서가 아니다. 그 조합으로 **설정(운영자) 화면이 손님 모니터에 박히는** 일이 생겼다.
        """
        primary = app.primaryScreen()
        others = [s for s in app.screens() if s is not primary]
        admin_scr = primary
        guest_scr = others[0] if others else None
        if swapped["on"] and guest_scr is not None:
            admin_scr, guest_scr = guest_scr, admin_scr
        _to_screen(stack, admin_scr)
        apply_dark_titlebar(int(stack.winId()))
        if guest_scr is not None:
            _to_screen(audience, guest_scr)
        else:
            audience.hide()      # 모니터 1대 — 손님 창은 F2로 필요할 때만
        stack.raise_(); stack.activateWindow()   # 조작은 운영자 창에서 시작
        setup.setFocus()

    def swap_screens():
        # F3: 운영자/손님 화면이 반대 모니터에 떴을 때 현장에서 즉시 맞바꾼다
        swapped["on"] = not swapped["on"]
        place_windows()
    _app_shortcut("F3", swap_screens)

    place_windows()

    QTimer.singleShot(300, auto_connect)  # 창 표시 후 자동 연결
    # 전달 서버는 시작할 때 미리 — 방화벽 허용 창을 손님 앞이 아니라 여기서 받는다
    QTimer.singleShot(900, controller.warmup_delivery)

    # 손님 접속 주소 자동 판정 — 랜선을 꽂거나 핫스팟을 켜면 운영자 화면 표시가 따라 바뀐다
    def _refresh_guest_addr():
        if setup.isVisible():            # 촬영 중엔 조회할 이유가 없다
            url, kind = controller.guest_endpoint()
            setup.set_guest_addr(url, kind)

    asked = {"once": False}

    def _ask_hotspot():
        """시작할 때 한 번, 핫스팟을 켜 달라고 요청한다(오너 운영 정책).

        ⚠️ 앱이 핫스팟을 켜지는 않는다 — 시스템 설정이고, 인터넷이 없으면 Windows 가 거부한다.
        대신 **부스를 열기 전에** 운영자가 손쓸 수 있는 시점에 말해 준다. 손님 앞에서 알게 되면 늦다.
        """
        if asked["once"]:
            return
        asked["once"] = True
        _, kind = controller.guest_endpoint()
        if kind == "핫스팟":
            return                        # 이미 켜져 있다 — 조용히 넘어간다
        box = QMessageBox(stack)
        box.setWindowTitle("손님 전달 준비")
        box.setIcon(QMessageBox.Information)
        if kind == "없음":
            box.setText(
                "인터넷·WiFi 연결이 없습니다.\n\n"
                "이 상태에서는 이 PC의 모바일 핫스팟도 켜지지 않습니다.\n"
                "인터넷 회선이 없는 ‘빈 공유기’라도 PC와 손님 폰을 같은 공유기에 연결하세요.\n"
                "(사진 전달에 인터넷은 필요하지 않습니다.)")
        else:
            box.setText(
                "시작하기 전에 이 PC의 모바일 핫스팟을 켜 주세요.\n\n"
                "장소 WiFi 는 비밀번호나 게스트망 격리 때문에 손님이 못 붙는 일이 잦습니다.\n"
                "핫스팟을 켜면 손님은 QR 두 장(WiFi · 사진)만으로 바로 받아갑니다.\n\n"
                f"지금 손님 접속 주소: {kind}")
        box.addButton("확인", QMessageBox.AcceptRole)
        box.exec_()
    addr_timer = QTimer(); addr_timer.setInterval(5000)
    addr_timer.timeout.connect(_refresh_guest_addr)
    addr_timer.start()
    QTimer.singleShot(1200, _refresh_guest_addr)
    QTimer.singleShot(1600, _ask_hotspot)   # 부스 열기 전에 한 번만 요청
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
