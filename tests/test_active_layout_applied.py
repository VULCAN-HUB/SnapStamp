"""시작할 때 **이름과 배치가 어긋나면 안 된다.**

실제 결함(2026-08-12): `active_layout` 은 아이돌형인데 저장된 `slots`/`canvas_size` 는 세로형인
설정으로 켜면, 화면엔 아이돌형으로 뜨는데 사진은 옛 칸에 들어간다 → "다른 레이아웃에서 비율 깨짐".
이름이 가리키는 항목을 시작 시 실제로 적용해야 한다.
"""
import pytest
from ui.setup_window import SetupWindow

IDOL = {"name": "아이돌형_테스트", "builtin": False, "template_path": "",
        "canvas_size": [1200, 1800],
        "slots": [{"x": 57, "y": 52 + i * 376, "w": 518, "h": 345} for i in range(4)],
        "even": False}


@pytest.fixture
def win(qapp):
    made = []

    def build(cfg):
        w = SetupWindow(cfg); made.append(w); return w
    yield build
    for w in made:
        w.close(); w.deleteLater()
    qapp.processEvents()


def test_startup_applies_the_named_layout(win):
    """config 의 slots 가 딴 레이아웃(세로형) 것이어도 active_layout 을 따른다."""
    cfg = {"camera": {"backend": "mock"},
           "user_layouts": [IDOL], "active_layout": IDOL["name"],
           "canvas_size": [640, 1920],                       # 옛 세로형 잔재
           "slots": [{"x": 26, "y": 48 + i * 390, "w": 589, "h": 368} for i in range(4)]}
    w = win(cfg)
    assert [w.editor.canvas_w, w.editor.canvas_h] == IDOL["canvas_size"]
    got = w.editor.get_slots()[0]
    assert (got["w"], got["h"]) == (518, 345), f"이름과 다른 칸이 적용됨: {got}"
    out = w.collect()
    assert out["canvas_size"] == IDOL["canvas_size"] and out["slots"][0]["w"] == 518


def test_matching_config_is_left_alone(win):
    """이름과 배치가 이미 맞으면 건드리지 않는다(사용자 편집 보존)."""
    cfg = {"camera": {"backend": "mock"}, "user_layouts": [IDOL],
           "active_layout": IDOL["name"],
           "canvas_size": list(IDOL["canvas_size"]),
           "slots": [dict(s) for s in IDOL["slots"]]}
    w = win(cfg)
    assert w.editor.get_slots() == [dict(s) for s in IDOL["slots"]]
