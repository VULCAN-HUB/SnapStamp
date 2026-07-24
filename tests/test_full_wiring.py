from pathlib import Path
from PIL import Image
from PyQt5.QtCore import QEventLoop, QTimer
from app.controller import AppController
from app.state import AppState
from core import uploader


def _cfg(sample):
    return {"camera": {"backend": "mock"}, "countdown_sec": 3, "trigger_key": "Space",
            "slots": [{"x": 0, "y": 0, "w": 100, "h": 100}, {"x": 100, "y": 0, "w": 100, "h": 100},
                      {"x": 0, "y": 100, "w": 100, "h": 100}, {"x": 100, "y": 100, "w": 100, "h": 100}],
            "template_path": ""}


def _samples(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        Image.new("RGB", (200, 200), (i * 40, 0, 0)).save(d / f"s{i}.jpg")


def test_full_chain_reaches_result(qapp, tmp_path, monkeypatch):
    _samples(tmp_path / "sample")
    monkeypatch.setattr(uploader, "upload_gofile", lambda p, timeout=10.0: "https://gofile.io/d/OK")
    out = tmp_path / "out"
    c = AppController(_cfg(str(tmp_path / "sample")), str(out))
    c.backend.sample_dir = str(tmp_path / "sample")
    results = []
    c.result_ready.connect(lambda fp, qr, mode: results.append((fp, qr, mode)))
    c.start_session()
    for _ in range(4):
        c.on_trigger()
        c.capture_current()
    # 합성 워커 완료 대기(비동기 → 이벤트루프 스핀)
    loop = QEventLoop(); c.result_ready.connect(lambda *a: loop.quit())
    QTimer.singleShot(5000, loop.quit)
    if not results:
        loop.exec_()
    assert results, "result_ready 시그널 미방출"
    fp, qr, mode = results[0]
    assert Path(fp).exists() and Path(qr).exists()
    assert mode in ("gofile", "local")


def test_second_session_liveview_reconnects(qapp, tmp_path, monkeypatch):
    # CRITICAL 리그레션 회귀 테스트: stop_liveview()가 frame_ready 연결을 끊으면
    # 2회차 start_session()에서 프레임이 재전달되지 않아 라이브뷰가 먹통이 된다.
    _samples(tmp_path / "sample")
    monkeypatch.setattr(uploader, "upload_gofile", lambda p, timeout=10.0: "https://gofile.io/d/OK")
    out = tmp_path / "out"
    c = AppController(_cfg(str(tmp_path / "sample")), str(out))
    c.backend.sample_dir = str(tmp_path / "sample")

    results = []
    c.result_ready.connect(lambda fp, qr, mode: results.append((fp, qr, mode)))
    c.start_session()
    for _ in range(4):
        c.on_trigger()
        c.capture_current()

    loop = QEventLoop(); c.result_ready.connect(lambda *a: loop.quit())
    QTimer.singleShot(5000, loop.quit)
    if not results:
        loop.exec_()
    assert results, "1회차 result_ready 시그널 미방출"

    # PROMPT → 트리거로 2회차 세션 재시작(리뷰 지시: on_trigger() 경로 사용)
    c._set(AppState.PROMPT)
    c.on_trigger()  # PROMPT 상태에서 트리거 → start_session() 재호출

    frame_count = [0]

    def _on_frame(img):
        frame_count[0] += 1
    c.frame_ready.connect(_on_frame)

    frame_loop = QEventLoop()
    c.frame_ready.connect(lambda *a: frame_loop.quit())
    QTimer.singleShot(2000, frame_loop.quit)
    frame_loop.exec_()

    assert frame_count[0] > 0, "2회차 세션에서 frame_ready가 재발행되지 않음(라이브뷰 먹통 회귀)"


def test_composite_failure_returns_to_idle(qapp, tmp_path):
    _samples(tmp_path / "sample")
    c = AppController(_cfg(str(tmp_path / "sample")), str(tmp_path / "out"))
    c.backend.sample_dir = str(tmp_path / "sample")
    errors = []
    c.error_occurred.connect(lambda m: errors.append(m))
    c.start_session()
    # 존재하지 않는 사진으로 합성 실패 유도
    c.photos = ["/nonexistent1.jpg", "/nonexistent2.jpg", "/nonexistent3.jpg", "/nonexistent4.jpg"]
    c._set(AppState.COMPOSITING)
    c.run_composite()
    c.comp_worker.wait(5000)
    qapp.processEvents()
    assert errors
    assert c.state == AppState.IDLE
    c.shutdown()
