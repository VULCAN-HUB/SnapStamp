"""손님(보조 모니터) 화면 — 페이지 전환과 컷바 배치.

실제 결함(2026-08-09): 컷바를 창의 resizeEvent 에서 배치하는 바람에 그 시점의 live_page 가
아직 옛 크기여서 컷바가 좌측에 붙었다(실기 실측: 보조 모니터 전체화면에서 x=61).
live_page 가 실제로 커진 순간에 다시 배치해야 한다.

⚠️ 이 테스트는 그 타이밍 자체를 재현하지는 못한다 — offscreen 에서는 창 resizeEvent
시점에 이미 live_page 크기가 맞아떨어져 옛 코드도 통과한다. 여기서 고정하는 것은
"컷바는 우측 상단"이라는 계약뿐이고, 타이밍은 실기 육안/스크린샷으로 확인해야 한다.
"""
from ui.audience_window import AudienceWindow, PAGE_READY, PAGE_LIVE, PAGE_RESULT


def test_pages_switch(qapp):
    w = AudienceWindow()
    w.show_live();        assert w.stack.currentIndex() == PAGE_LIVE
    w.show_result_page(); assert w.stack.currentIndex() == PAGE_RESULT
    w.show_ready();       assert w.stack.currentIndex() == PAGE_READY


def test_cut_bar_stays_top_right_after_resize(qapp):
    w = AudienceWindow()
    w.show_live()
    w.resize(1920, 1080)
    qapp.processEvents()
    right_gap = w.live_page.width() - (w.cut_bar.x() + w.cut_bar.width())
    assert 0 <= right_gap <= 40, f"컷바가 우측 상단이 아님 (오른쪽 여백 {right_gap}px)"
    assert w.cut_bar.y() <= 40
