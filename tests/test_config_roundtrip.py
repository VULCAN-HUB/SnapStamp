"""설정을 저장했다 다시 켜도 **사용자 배치가 그대로여야 한다**.

실제 결함(2026-08-14): 라이브러리에 없는 배치(구버전 설정 등)로 켜면 콤보 첫 항목인 **예시 이름이
`active_layout` 으로 저장**되고, 다음 실행에서 "이름과 배치 일치" 로직이 그 예시 배치로
**사용자 슬롯을 덮어썼다**(800×600 · 200×150 → 640×1920 · 589×368).
"""
import pytest
from ui.setup_window import SetupWindow
from core.layouts import LAYOUTS

LEGACY = {"camera": {"backend": "mock"}, "countdown_sec": 3, "trigger_key": "Space",
          "canvas_size": [800, 600],
          "slots": [{"x": 10, "y": 10 + i * 100, "w": 200, "h": 150} for i in range(4)]}


@pytest.fixture
def make(qapp):
    made = []

    def build(cfg):
        w = SetupWindow(cfg); made.append(w); return w
    yield build
    for w in made:
        w.close(); w.deleteLater()
    qapp.processEvents()


def test_unknown_layout_survives_a_restart(make):
    saved = make(dict(LEGACY)).collect()
    assert saved["active_layout"] == "", "라이브러리에 없는 배치인데 예시 이름이 활성으로 저장됐다"

    again = make(saved).collect()
    assert again["slots"] == saved["slots"], "재시작에 사용자 배치가 바뀌었다"
    assert again["canvas_size"] == saved["canvas_size"]


def test_named_layout_still_round_trips(make):
    """이름이 실제 항목을 가리키면 그 배치를 그대로 유지한다(기존 동작 보존)."""
    name = list(LAYOUTS)[0]
    lay = LAYOUTS[name]
    cfg = dict(LEGACY, active_layout=name,
               canvas_size=list(lay["canvas_size"]),
               slots=[dict(s) for s in lay["slots"]])
    out = make(cfg).collect()
    assert out["active_layout"] == name
    assert out["slots"] == [dict(s) for s in lay["slots"]]
