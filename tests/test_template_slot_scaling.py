"""템플릿을 추가하면 칸을 **알아서 맞춘다** — 순서: 구멍 인식 → 예시 배치 → 비율 보존 축소.

오너 요구(2026-08-12): "제작할 때 준 세로형·아이돌형 예시를 기준으로 초기 위치를 잡거나,
프로그램이 PNG의 빈 공간을 찾아 사진 자리를 잡으면 안 되나?" → 둘 다 한다.

과거 결함: 가로·세로 배율을 따로 곱해 칸이 1.50 → 0.75(세로)로 뒤집혔다
(`518×(640/1200)=276`, `345×(1920/1800)=368`). 마지막 폴백은 반드시 비율을 보존해야 한다.
"""
import pytest
from PIL import Image
from ui.setup_window import SetupWindow
from core.layouts import LAYOUTS


@pytest.fixture
def win(qapp):
    cfg = {"camera": {"backend": "mock"}, "canvas_size": [1200, 1800],
           "slots": [{"x": 57, "y": 52 + i * 376, "w": 518, "h": 345} for i in range(4)]}
    w = SetupWindow(cfg)
    yield w
    w.close(); w.deleteLater(); qapp.processEvents()


def _holes(size, boxes, path):
    """사진 자리를 투명하게 뚫은 템플릿(오너 템플릿과 같은 방식)."""
    im = Image.new("RGBA", size, (30, 30, 30, 255))
    for x, y, w, h in boxes:
        im.paste((0, 0, 0, 0), (x, y, x + w, y + h))
    im.save(path)


def test_transparent_holes_become_the_slots(win, tmp_path):
    tpl = tmp_path / "holes.png"
    boxes = [(40, 60 + i * 400, 560, 350) for i in range(4)]     # 1.60
    _holes((640, 1920), boxes, tpl)

    win._add_template_layout(str(tpl))

    got = win.editor.get_slots()
    assert len(got) == 4
    for s, (x, y, w, h) in zip(got, boxes):
        assert abs(s["w"] - w) <= 3 and abs(s["h"] - h) <= 3, f"칸이 구멍과 다르다: {s}"
        assert abs(s["x"] - x) <= 3 and abs(s["y"] - y) <= 3


def test_falls_back_to_the_matching_example_layout(win, tmp_path):
    """구멍이 없으면 **같은 용지 비율의 예시 배치**를 초기값으로."""
    tpl = tmp_path / "plain.png"
    Image.new("RGB", (640, 1920), "white").save(tpl)      # 2:6 = 세로형 예시와 같은 비율

    win._add_template_layout(str(tpl))

    want = LAYOUTS["세로형 (4:2.5 · 2x6인치)"]["slots"][0]
    got = win.editor.get_slots()[0]
    assert (got["w"], got["h"]) == (want["w"], want["h"]), f"예시 배치가 안 들어옴: {got}"


def test_odd_canvas_keeps_slot_ratio(win, tmp_path):
    """예시와 비율이 다른 용지면 마지막 폴백 — 칸 비율은 절대 안 뒤집힌다."""
    tpl = tmp_path / "odd.png"
    Image.new("RGB", (900, 1000), "white").save(tpl)
    before = [s["w"] / s["h"] for s in win.editor.get_slots()]

    win._add_template_layout(str(tpl))

    for got, want in zip((s["w"] / s["h"] for s in win.editor.get_slots()), before):
        assert abs(got - want) < 0.01, f"칸 비율이 바뀌었다: {got:.3f} != {want:.3f}"
    for s in win.editor.get_slots():
        assert 0 <= s["x"] and s["x"] + s["w"] <= 900
        assert 0 <= s["y"] and s["y"] + s["h"] <= 1000
