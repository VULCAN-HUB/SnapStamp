import sys
import json
from pathlib import Path
from PyQt5.QtCore import (Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation,
                          QEasingCurve)
from PyQt5.QtWidgets import (QApplication, QStackedWidget, QGraphicsOpacityEffect,
                             QMessageBox, QShortcut)
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

    _fade = {}  # 위젯별 페이드 애니메이션 보관

    def switch_to(widget):
        # 부드러운 페이드 인 전환
        stack.setCurrentWidget(widget)
        widget.setFocus()  # 스페이스바 입력(시작/더블탭)을 현재 화면이 받도록
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity")
        anim.setDuration(280); anim.setStartValue(0.0); anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        _fade[widget] = anim
        anim.start()

    # 라이브 프레임은 촬영화면·설정 미리보기·관객 창 모두에 전달(관객 창은 항상 미러링)
    controller.frame_ready.connect(shoot.on_frame)
    controller.frame_ready.connect(setup.show_preview_frame)
    controller.frame_ready.connect(audience.on_frame)
    controller.frame_ready.connect(attract.on_frame)
    controller.shot_captured.connect(shoot.set_cut_thumbnail)

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
    controller.result_ready.connect(
        lambda fp, qr, mode: (
            result.set_reveal_enabled(controller.config.get("reveal_enabled", True),
                                      controller.config.get("reveal_sec", 2)),
            result.show_result(fp, qr, mode, _wifi_qr_path(),
                               controller.config.get("gif_enabled", True)),
            switch_to(result)))

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
            if stack.currentWidget() is not shoot:
                switch_to(shoot)  # 대기 화면에서 트리거 → 촬영 화면으로 전환
            run_countdown(controller.config.get("countdown_sec", 3))
        elif s == AppState.PREVIEW:
            shoot.set_shot_count(len(controller.photos))
            shoot.set_hint("버튼을 눌러 다음 컷을 촬영하세요")
            audience.set_hint(f"{len(controller.photos)} / 4 컷 · 다음 컷을 준비하세요 📸")
            # 촬영 도중 손님이 가버린 경우 대비 — 컷마다 방치 타이머 재무장
            _arm_idle(controller.config.get("abandon_timeout_sec", 60),
                      _abandon_session, "{n}초 뒤에 처음으로 돌아갑니다 · 촬영한 컷은 취소됩니다")
        elif s == AppState.IDLE:
            # 유휴(=다음 손님 준비) → 시네마틱 대기 화면
            shoot.set_shot_count(0)
            shoot.set_hint("버튼을 눌러 촬영을 시작하세요")
            audience.set_hint("곧 촬영을 시작합니다 📸")
            if stack.currentWidget() is not attract:
                switch_to(attract)
            else:
                attract.setFocus()
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
        # 준비 화면 방치 → 대기 화면으로(찍은 컷 없음)
        if controller.state == AppState.IDLE and stack.currentWidget() is shoot:
            switch_to(attract)

    def _abandon_session():
        # 촬영 도중 방치 → 찍힌 컷 폐기하고 다음 손님 대기로
        if controller.state == AppState.PREVIEW:
            controller.discard_session()

    def go_ready():
        """대기 화면에서 트리거 1회 → 촬영(준비) 화면만 표시. 카운트다운은 아직 시작 안 함.
        손님이 전체화면으로 자기 모습을 보고 자세를 잡은 뒤, 한 번 더 눌러야 촬영이 시작된다."""
        if controller.state != AppState.IDLE:
            return
        if stack.currentWidget() is not shoot:
            switch_to(shoot)
        shoot.set_hint("준비되면 버튼을 한 번 더 눌러 촬영을 시작하세요")
        audience.set_hint("준비되면 버튼을 눌러주세요 📸")
        _arm_idle(controller.config.get("ready_timeout_sec", 30),
                  _back_to_attract, "{n}초 뒤에 처음으로 돌아갑니다")
    attract.start_requested.connect(go_ready)  # 대기 화면 트리거 → 촬영 준비 화면

    def start():
        # 미리보기로 이미 연결된 카메라를 그대로 재사용 → 재연결 없이 즉시 대기 화면으로.
        new_cfg = setup.collect()
        _save_config(new_cfg)  # 설정 영구 저장(다음 실행 시 자동 복원)
        controller.apply_settings(new_cfg, new_cfg.get("save_path", save_dir))
        trigger = new_cfg.get("trigger_key", "Space")
        shoot.rebind_trigger(trigger)
        result.set_trigger(trigger)     # 완성 화면 재시작 트리거
        attract.set_trigger(trigger)    # 대기 화면 시작 트리거
        controller.begin_session()      # IDLE → on_state 가 대기 화면으로 전환
    setup.start_requested.connect(start)

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
        if cam.get("backend") == "webcam" and cam.get("device_name"):
            setup.backend_box.setCurrentText("webcam")
            test_camera()
            return
        # 저장된 카메라가 없을 때만 백그라운드 감지(UI 안 멈춤)
        def on_found(cams):
            setup.set_camera_list(cams)
            if cams:
                setup.backend_box.setCurrentText("webcam")
                test_camera()
        scan_cameras(on_found)

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
    QShortcut(QKeySequence("Ctrl+Q"), stack, activated=safe_quit)  # 어디서든 안전 종료

    def toggle_main_fullscreen():
        # F11: 메인 창 전체화면 ↔ 창모드(창모드에서 자유 이동/크기조절 가능)
        if stack.isFullScreen():
            stack.showNormal(); stack.resize(1280, 800)
        else:
            stack.showFullScreen()
    QShortcut(QKeySequence("F11"), stack, activated=toggle_main_fullscreen)

    def toggle_audience():
        # F2: 관객(보조 모니터) 창 열기/닫기
        if audience.isVisible():
            audience.hide()
        else:
            audience.show(); audience.raise_()
    QShortcut(QKeySequence("F2"), stack, activated=toggle_audience)

    stack.setWindowTitle("SnapStamp — Event Photobooth")
    stack.showFullScreen()
    setup.setFocus()
    apply_dark_titlebar(int(stack.winId()))

    # 보조 모니터가 있으면 관객 창을 거기 전체화면으로 자동 표시(없으면 숨김 — F2로 열기)
    screens = app.screens()
    if len(screens) > 1:
        geo = screens[1].geometry()
        audience.move(geo.x(), geo.y())
        audience.showFullScreen()

    QTimer.singleShot(300, auto_connect)  # 창 표시 후 자동 연결
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
