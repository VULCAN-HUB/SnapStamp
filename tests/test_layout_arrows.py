"""좌우 방향키 레이아웃 전환 — 내가 등록한 레이아웃만 순환한다(예시 제외).

오너 요구(2026-08-09): "여러 레이아웃 등록했을 때 방향키 좌우로 전환. 단 예시 레이아웃은 안 나오게."
같은 키가 슬롯 미세이동에도 쓰이므로 **칸을 고른 채 편집 중일 땐 전환하지 않는다**.
"""
import pytest
from PyQt5.QtWidgets import QLineEdit
from ui.setup_window import SetupWindow
from core.layouts import LAYOUTS


def _user(name):
    return {"name": name, "builtin": False, "template_path": "", "canvas_size": [1200, 1800],
            "slots": [{"x": 50, "y": 50 + i * 400, "w": 500, "h": 330} for i in range(4)],
            "even": False}


def _win(qapp, users, active=None):
    cfg = {"camera": {"backend": "mock"}, "user_layouts": users}
    if active:
        cfg["active_layout"] = active
    return SetupWindow(cfg)


@pytest.fixture
def win(qapp):
    w = _win(qapp, [_user("행사A"), _user("행사B"), _user("행사C")], "행사A")
    yield w
    w.close(); w.deleteLater(); qapp.processEvents()


def test_cycles_only_user_layouts(win):
    assert win._step_user_layout(1) and win._active_layout == "행사B"
    assert win._step_user_layout(1) and win._active_layout == "행사C"
    win._step_user_layout(1)
    assert win._active_layout == "행사A", "마지막에서 처음으로 돌아와야 한다"
    win._step_user_layout(-1)
    assert win._active_layout == "행사C", "왼쪽은 반대 방향"


def test_examples_are_never_selected(win):
    seen = set()
    for _ in range(8):
        win._step_user_layout(1)
        seen.add(win._active_layout)
    assert seen == {"행사A", "행사B", "행사C"}
    assert not (seen & set(LAYOUTS)), "예시 레이아웃이 방향키 순환에 끼어들면 안 된다"


def test_from_example_jumps_into_user_layouts(qapp):
    w = _win(qapp, [_user("행사A")], list(LAYOUTS)[0])
    try:
        assert w._step_user_layout(1) and w._active_layout == "행사A"
    finally:
        w.close(); w.deleteLater(); qapp.processEvents()


def test_no_user_layouts_means_no_op(qapp):
    w = _win(qapp, [])
    try:
        assert w._step_user_layout(1) is False
    finally:
        w.close(); w.deleteLater(); qapp.processEvents()


def test_arrows_yield_to_slot_editing_and_text_input(win, qapp):
    win.editor.sel = 0                      # 칸을 고른 상태 = 미세이동 중
    assert win._arrows_free() is False

    win.editor.sel = None
    assert win._arrows_free() is True, "선택을 풀면 전환 가능"
    # 숨겨진 창에서는 실제 포커스가 잡히지 않으므로 대상 위젯을 직접 넘겨 확인한다
    assert win._arrows_free(QLineEdit(win)) is False, "입력칸에서 방향키를 뺏으면 안 된다"
