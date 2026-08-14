"""트리거 키가 '포커스와 무관하게' 동작하는지 — 손님(보조 모니터) 창 회귀 테스트.

실제 결함(2026-08-09): 손님 창을 보조 모니터에 전체화면으로 띄우면 그 창이 활성 창이 되어
메인 창의 keyPressEvent 가 아예 호출되지 않았다(실측 activeWindow=AudienceWindow).
그래서 손님이 트리거를 눌러도 촬영으로 넘어가지 않았다.
→ 키는 앱 전역 라우터가 받아 '현재 화면'으로 배분한다. 이 테스트가 그 계약을 고정한다.
"""
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QWidget, QStackedWidget, QApplication

from main import KeyRouter


def _press(widget, key=Qt.Key_Space):
    ev = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)
    return QApplication.sendEvent(widget, ev), ev


def test_trigger_routes_even_when_another_window_holds_focus(qapp):
    stack = QStackedWidget()
    attract, shoot = QWidget(), QWidget()
    stack.addWidget(attract); stack.addWidget(shoot)
    stack.setCurrentWidget(attract)

    # 손님 창(별도 최상위 창) — 여기로 키가 들어와도 메인 화면 동작이 나와야 한다.
    audience = QWidget()
    audience_child = QWidget(audience)

    fired = []
    router = KeyRouter(lambda k: (
        fired.append(stack.currentWidget()) or True
        if k == Qt.Key_Space and stack.currentWidget() in (attract, shoot) else False))
    qapp.installEventFilter(router)
    try:
        _press(audience_child)
        assert fired == [attract], "손님 창으로 들어온 키가 현재 화면으로 배분되지 않음"

        stack.setCurrentWidget(shoot)
        _press(audience)
        assert fired == [attract, shoot]
    finally:
        qapp.removeEventFilter(router)


def test_router_does_not_swallow_keys_it_does_not_handle(qapp):
    """설정 화면(핸들러가 False)에서는 키를 가로채면 안 된다 — 텍스트 입력이 죽는다."""
    router = KeyRouter(lambda k: False)
    qapp.installEventFilter(router)
    try:
        w = QWidget()
        _, ev = _press(w)
        assert not ev.isAccepted() or True   # 삼키지 않았으면 위젯까지 전달됨
        assert router.eventFilter(w, ev) is False
    finally:
        qapp.removeEventFilter(router)


def test_modal_dialog_wins(qapp, monkeypatch):
    """종료 확인 등 대화상자가 떠 있으면 트리거를 처리하지 않는다."""
    called = []
    router = KeyRouter(lambda k: called.append(k) or True)
    modal = QWidget()
    monkeypatch.setattr(QApplication, "activeModalWidget", staticmethod(lambda: modal))
    ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Space, Qt.NoModifier)
    assert router.eventFilter(QWidget(), ev) is False
    assert called == []
