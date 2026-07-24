from pathlib import Path
from PIL import Image
from app.state import AppState
from app.controller import AppController


def _cfg(sample_dir):
    return {"camera": {"backend": "mock"}, "countdown_sec": 3, "slots": [
        {"x": 0, "y": 0, "w": 100, "h": 100}, {"x": 100, "y": 0, "w": 100, "h": 100},
        {"x": 0, "y": 100, "w": 100, "h": 100}, {"x": 100, "y": 100, "w": 100, "h": 100}]}


def _samples(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        Image.new("RGB", (200, 200), (i * 40, 0, 0)).save(d / f"s{i}.jpg")


def test_controller_start_goes_idle(qapp, tmp_path):
    _samples(tmp_path / "sample")
    c = AppController(_cfg(str(tmp_path / "sample")), str(tmp_path / "out"))
    c.backend.sample_dir = str(tmp_path / "sample")
    seen = []
    c.state_changed.connect(lambda s: seen.append(s))
    c.start_session()
    try:
        assert c.state == AppState.IDLE
        assert AppState.IDLE in seen
    finally:
        # Phase 3: start_session()이 라이브뷰 스레드를 구동하므로 명시적으로 정지
        # (그렇지 않으면 다음 테스트로 스레드가 넘어가 offscreen 플랫폼에서 불안정해짐).
        c.stop_liveview()
        qapp.processEvents()


def test_controller_four_shots_reach_compositing(qapp, tmp_path):
    _samples(tmp_path / "sample")
    c = AppController(_cfg(str(tmp_path / "sample")), str(tmp_path / "out"))
    c.backend.sample_dir = str(tmp_path / "sample")
    c.start_session()
    try:
        # 4회 촬영 시뮬레이션
        for _ in range(4):
            c.on_trigger()            # IDLE/PREVIEW → COUNTDOWN
            c.capture_current()       # SHOOTING → PREVIEW (컷 누적)
        assert len(c.photos) == 4
        assert c.state == AppState.COMPOSITING
    finally:
        c.stop_liveview()
        if c.comp_worker is not None:
            c.comp_worker.wait(3000)
        qapp.processEvents()
