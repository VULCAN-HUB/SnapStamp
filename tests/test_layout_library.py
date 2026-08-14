"""레이아웃마다 사진 칸이 따로 놀아야 한다 — 편집 격리 회귀 테스트.

실제 결함(2026-08-09): 활성 레이아웃의 출처가 두 개(`_active_layout` vs 콤보 currentData)라
**2번 레이아웃을 편집했는데 1번 항목에 저장되는** 일이 재현됐다. 오너 요구는 명확하다 —
"세로형 맞췄는데 아이돌형이 변하면 안 되고, 아이돌형1 옮겼다고 아이돌형2가 변하면 안 된다."
"""
import pytest
from ui.setup_window import SetupWindow
from core.layouts import LAYOUTS


def _user(name, x):
    return {"name": name, "builtin": False, "template_path": "", "canvas_size": [1200, 1800],
            "slots": [{"x": x, "y": 50 + i * 400, "w": 500, "h": 330} for i in range(4)],
            "even": False}


@pytest.fixture
def win(qapp):
    cfg = {"camera": {"backend": "mock"},
           "user_layouts": [_user("아이돌형1", 57), _user("아이돌형2", 57)],
           "active_layout": "아이돌형1"}
    w = SetupWindow(cfg)
    yield w
    # ⚠️ 창을 그냥 두면 인터프리터 종료 때 Qt 가 이미 정리된 뒤에 소멸자가 돌아
    #    access violation 으로 죽는다(전체 스위트 실행에서 실측). 여기서 확실히 닫는다.
    w.close()
    w.deleteLater()
    qapp.processEvents()


def _first(win, name):
    e = win._find_entry(name)
    return (e["slots"][0]["x"], e["slots"][0]["y"])


def test_edit_lands_on_the_layout_being_edited(win):
    win._select_layout("아이돌형2")
    win.editor.slots[0]["y"] = 777
    win._on_slots_edited()
    assert _first(win, "아이돌형2") == (57, 777), "편집한 레이아웃에 저장되지 않음"
    assert _first(win, "아이돌형1") == (57, 50), "다른 레이아웃이 함께 바뀜"


def test_edits_survive_switching_back(win):
    win._select_layout("아이돌형1")
    win.editor.slots[0]["x"] = 999
    win._on_slots_edited()
    win._select_layout("아이돌형2")
    win._select_layout("아이돌형1")
    assert (win.editor.slots[0]["x"], win.editor.slots[0]["y"]) == (999, 50)


def test_editing_an_example_creates_a_user_copy(win):
    """예시는 편집을 담을 곳이 없다 → 사본으로 승격. 예시 원본은 안 변한다(조용한 실패 금지)."""
    name = list(LAYOUTS)[0]
    before = [dict(s) for s in LAYOUTS[name]["slots"]]
    win._select_layout(name)
    win.editor.slots[0]["x"] = 123
    win._on_slots_edited()
    assert LAYOUTS[name]["slots"] == before, "예시 원본이 오염됨"
    copies = [u for u in win.user_layouts if u["name"].startswith(name)]
    assert copies and copies[0]["slots"][0]["x"] == 123, "편집이 사본에 저장되지 않음"
    assert win._active_layout == copies[0]["name"]
