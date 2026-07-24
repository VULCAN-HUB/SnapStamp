from pathlib import Path
from PIL import Image
from core.workers.compositor_worker import CompositorWorker


def _photos(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    ps = []
    for i in range(4):
        p = d / f"p{i}.jpg"; Image.new("RGB", (200, 200), (i * 50, 80, 80)).save(p); ps.append(str(p))
    return ps


def test_compositor_worker_success(qapp, tmp_path):
    photos = _photos(tmp_path)
    slots = [{"x": 0, "y": 0, "w": 100, "h": 100}, {"x": 100, "y": 0, "w": 100, "h": 100},
             {"x": 0, "y": 100, "w": 100, "h": 100}, {"x": 100, "y": 100, "w": 100, "h": 100}]
    out = tmp_path / "final.jpg"
    done = []
    w = CompositorWorker(None, slots, photos, str(out), canvas_size=(200, 200))
    w.composite_done.connect(lambda p: done.append(p))
    w.run()  # 동기 실행으로 결정적 테스트
    assert done and Path(done[0]).exists()


def test_compositor_worker_failure_signal(qapp, tmp_path):
    slots = [{"x": 0, "y": 0, "w": 100, "h": 100}]
    fail = []
    w = CompositorWorker(None, slots, ["/nonexistent.jpg"], str(tmp_path / "x.jpg"), canvas_size=(200, 200))
    w.composite_failed.connect(lambda m: fail.append(m))
    w.run()
    assert fail
