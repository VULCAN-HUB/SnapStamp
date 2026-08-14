"""손님 화면에는 **운영자가 넣은 레이아웃만** 보인다 — 예시(빌트인)는 안 나온다.

오너 지시(2026-08-12): "예시용 레이아웃이 촬영 준비 화면에 같이 나온다. 커스텀만 나오게."
`_step_user_layout` 이 예시를 건너뛰는지, 활성이 예시일 때 내 레이아웃으로 넘어가는지 고정한다.
"""
import pytest
from ui.setup_window import SetupWindow
from core.layouts import LAYOUTS


def _user(name):
    return {"name": name, "builtin": False, "template_path": "", "canvas_size": [1200, 1800],
            "slots": [{"x": 50, "y": 50 + i * 400, "w": 500, "h": 333} for i in range(4)],
            "even": False}


@pytest.fixture
def make(qapp):
    made = []

    def build(users, active=None):
        cfg = {"camera": {"backend": "mock"}, "user_layouts": users}
        if active:
            cfg["active_layout"] = active
        w = SetupWindow(cfg); made.append(w); return w
    yield build
    for w in made:
        w.close(); w.deleteLater()
    qapp.processEvents()


def test_example_is_never_in_the_cycle(make):
    w = make([_user("행사A"), _user("행사B")], "행사A")
    seen = set()
    for _ in range(6):
        w._step_user_layout(1)
        seen.add(w._active_layout)
    assert seen == {"행사A", "행사B"}
    assert not (seen & set(LAYOUTS)), "예시가 손님 순환에 끼었다"


def test_active_example_jumps_to_a_custom_layout(make):
    """예시가 활성인 채로 시작해도 내 레이아웃으로 넘어간다."""
    w = make([_user("행사A")], list(LAYOUTS)[0])
    assert w._step_user_layout(1) is True
    assert w._active_layout == "행사A"


def test_no_custom_layouts_means_nothing_to_cycle(make):
    """등록한 게 없으면 예시로 대체하지 않는다 — 손님에게 보여줄 것이 없는 게 맞다."""
    w = make([], list(LAYOUTS)[0])
    assert w._step_user_layout(1) is False
    assert w._active_layout in LAYOUTS       # 운영자 화면에서는 예시를 계속 볼 수 있다
