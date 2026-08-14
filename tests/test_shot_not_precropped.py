"""컷마다 **자기 칸 비율**로 한 번만 자른다 — 그래야 합성이 더 안 자른다.

실제 결함(2026-08-12): 촬영본을 '첫 칸(대표) 비율'로 잘라 저장했더니, 칸마다 비율이 다른
레이아웃에서 합성 때 `cover_fit` 이 **또** 잘라 비율이 깨졌다. 해결은 크롭을 없애는 게 아니라
**그 컷이 들어갈 칸의 비율로 맞추는 것** — 그러면 cover_fit 은 크기만 바꾼다(추가 잘림 0).
"""
from PIL import Image
from app.controller import AppController
from app.state import AppState
from core.compositor import cover_fit

MIXED = [{"x": 0, "y": 0, "w": 600, "h": 400},      # 1.50
         {"x": 0, "y": 0, "w": 400, "h": 400},      # 1.00
         {"x": 0, "y": 0, "w": 640, "h": 400},      # 1.60
         {"x": 0, "y": 0, "w": 500, "h": 400}]      # 1.25


def _cfg(slots):
    return {"camera": {"backend": "mock"}, "slots": slots, "canvas_size": [1200, 1800],
            "gif_enabled": False, "keep_cuts": False}


def test_each_shot_matches_its_own_slot_ratio(tmp_path, qapp):
    c = AppController(_cfg(MIXED), str(tmp_path))
    c.backend.connect()
    for i, s in enumerate(MIXED):
        c._set(AppState.COUNTDOWN)
        c.capture_current()
        with Image.open(c.photos[i]) as im:
            got, want = im.size[0] / im.size[1], s["w"] / s["h"]
        assert abs(got - want) < 0.01, f"{i}번 컷 비율 {got:.3f} != 칸 {want:.3f}"


def test_composite_does_not_crop_further(tmp_path, qapp):
    """촬영본 비율 = 칸 비율이면 cover_fit 은 잘라내지 않고 크기만 맞춘다."""
    c = AppController(_cfg(MIXED), str(tmp_path))
    c.backend.connect()
    c._set(AppState.COUNTDOWN)
    c.capture_current()
    with Image.open(c.photos[0]) as im:
        shot = im.convert("RGB")
        s = MIXED[0]
        out = cover_fit(shot, s["w"], s["h"])
        assert out.size == (s["w"], s["h"])
        # 잘림이 없으면 원본을 그대로 축소한 것과 같다
        assert abs(shot.size[0] / shot.size[1] - out.size[0] / out.size[1]) < 0.01
