"""손님용 보조 모니터 화면 — 관리자 없이 손님끼리 진행할 수 있게 전 과정을 보여준다.

관리자 화면(설정·요약·에디터)과 철저히 분리. 손님 모니터에 뜨는 것만:
  1) 촬영 전 준비 화면(브랜드 + 시작 방법 안내)
  2) 촬영 중 라이브 화면
  3) 촬영된 컷 — **우측 상단에 4개**
  4) 완성 사진(레이아웃 적용본)
  5) 다운로드 QR — WiFi · 사진 · 움짤
  6) 다음 손님을 위한 재시작 방법(트리거 키 안내)

준비 화면과 완성 화면은 운영자 화면과 같은 위젯(`AttractWindow`·`ResultWindow`)을 재사용한다.
손님 화면은 **표시 전용** — 여기서 나온 재시작 시그널은 배선하지 않는다.
"""
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
                             QStackedWidget)
from ui.theme import MUTED, ACCENT
from ui.shoot_window import CountdownRing, _ColorOverlay, CELL_EMPTY, CELL_FULL
from ui.result_window import ResultWindow
from ui.attract_window import AttractWindow

PAGE_READY, PAGE_LIVE, PAGE_RESULT = 0, 1, 2


class AudienceWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("SnapStamp — 손님 화면")
        self.setStyleSheet("background:#000000;")
        self.resize(960, 600)
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # ── 0) 준비 화면 ──
        self.attract = AttractWindow()
        self.stack.addWidget(self.attract)

        # ── 1) 촬영(라이브뷰 + 우측 상단 컷 4개) ──
        self.live_page = QWidget(); self.live_page.setStyleSheet("background:#000000;")
        lv = QVBoxLayout(self.live_page); lv.setContentsMargins(0, 0, 0, 0); lv.setSpacing(0)
        # 준비 단계: 좌 = 고른 디자인(크게), 우 = 라이브뷰. 촬영이 시작되면 좌측은 접히고
        # 라이브뷰가 화면을 다 쓴다(찍는 순간엔 자기 모습이 커야 한다).
        split = QHBoxLayout(); split.setContentsMargins(0, 0, 0, 0); split.setSpacing(0)
        lv.addLayout(split, 1)
        self.view = QLabel(); self.view.setAlignment(Qt.AlignCenter)
        self.view.setText("카메라 대기 중…")
        self.view.setStyleSheet(f"color:{MUTED}; font-size:30px; background:#000000;")
        self.view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.view.setMinimumSize(1, 1)
        # ── 좌측: 지금 고른 디자인(실제 모습) ──
        self.design = QWidget()
        self.design.setStyleSheet("background:#0A0D12; border-right:1px solid #222831;")
        dv = QVBoxLayout(self.design); dv.setContentsMargins(24, 20, 24, 20); dv.setSpacing(12)
        self.design_name = QLabel("디자인")
        self.design_name.setAlignment(Qt.AlignCenter)
        self.design_name.setStyleSheet("color:#EEF1F7; font-size:30px; font-weight:bold;")
        dv.addWidget(self.design_name)
        self.design_prev = QLabel()
        self.design_prev.setAlignment(Qt.AlignCenter)
        self.design_prev.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.design_prev.setMinimumSize(1, 1)
        self.design_prev.setStyleSheet("background:transparent;")
        dv.addWidget(self.design_prev, 1)
        self.design_tip = QLabel("◀ ▶ 로 디자인 고르기")
        self.design_tip.setAlignment(Qt.AlignCenter)
        self.design_tip.setStyleSheet("color:#FFD98A; font-size:24px; font-weight:bold;")
        dv.addWidget(self.design_tip)
        self.design.hide()          # 고를 게 없으면(등록 레이아웃 1개 이하) 안 띄운다
        self._design_pm = None      # 원본 픽스맵(창 크기 바뀌면 다시 스케일)
        split.addWidget(self.design, 4)
        split.addWidget(self.view, 6)

        self.hint = QLabel("곧 촬영을 시작합니다 📸")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet(
            f"color:white; font-size:32px; font-weight:bold; background:{ACCENT}; padding:18px;")
        lv.addWidget(self.hint)

        # 컷 스트립 — 라이브 위 '우측 상단'에 떠 있는 오버레이(레이아웃에 자리 안 뺏김)
        self.cut_bar = QWidget(self.live_page)
        self.cut_bar.setStyleSheet("background:rgba(0,0,0,0.55); border-radius:12px;")
        cb = QVBoxLayout(self.cut_bar); cb.setContentsMargins(12, 10, 12, 12); cb.setSpacing(8)
        self.counter = QLabel("0 / 4")
        self.counter.setAlignment(Qt.AlignCenter)
        self.counter.setStyleSheet("color:#EEF1F7; font-size:22px; font-weight:bold;")
        cb.addWidget(self.counter)
        self.cut_cells = []
        for _ in range(4):
            c = QLabel(); c.setFixedSize(150, 112); c.setStyleSheet(CELL_EMPTY)
            self.cut_cells.append(c); cb.addWidget(c)
        self.cut_bar.adjustSize()
        # ⚠️ 창의 resizeEvent 로 배치하면 안 된다 — 그 시점엔 live_page 가 아직 옛 크기라
        #    컷바가 좌측에 붙는다(실측: 1920 창에서 live_page.width()=639 로 계산됨).
        #    live_page 가 실제로 커진 순간에 다시 배치한다.
        self.live_page.installEventFilter(self)
        self.stack.addWidget(self.live_page)

        # ── 2) 완성 사진 + QR 3종 + 재시작 안내 ──
        self.result = ResultWindow()
        self.result.setFocusPolicy(Qt.NoFocus)   # 표시 전용(시그널 미배선)
        self.stack.addWidget(self.result)

        # 오버레이(카운트다운·플래시)는 창 전체에 덮는다
        self.countdown = CountdownRing(self); self.countdown.hide()
        self.flash_ov = _ColorOverlay("white", self)
        self.flash_ov.hide()

    # ── 페이지 전환 ──
    def show_ready(self):
        self.stack.setCurrentIndex(PAGE_READY)

    def show_live(self):
        self.stack.setCurrentIndex(PAGE_LIVE)
        self._place_cut_bar()

    def eventFilter(self, obj, ev):
        if obj is self.live_page and ev.type() == QEvent.Resize:
            self._place_cut_bar()
            self._place_design()
        return super().eventFilter(obj, ev)

    def show_result_page(self):
        self.stack.setCurrentIndex(PAGE_RESULT)

    def set_trigger(self, key):
        """시작·재시작 안내 문구에 실제 트리거 키를 반영(손님이 스스로 진행)."""
        self.attract.set_trigger(key)
        self.result.set_trigger(key)

    def resizeEvent(self, e):
        self.countdown.setGeometry(self.rect())
        self.flash_ov.setGeometry(self.rect())
        self._place_cut_bar()
        super().resizeEvent(e)

    def set_design(self, name: str, pixmap=None, choosable: bool = True):
        """지금 고른 디자인을 좌측에 크게 보여준다. 고를 게 없으면 좌측 칸 자체를 접는다."""
        # ⚠️ 등록 레이아웃이 하나뿐이어도 **디자인은 보여준다** — 손님이 무엇으로 찍히는지
        #    알아야 한다. 숨기는 건 '고르기 안내'뿐(고를 게 없는데 ◀▶ 를 띄우면 거짓말).
        if not name:
            self.design.hide(); return
        self.design_tip.setVisible(bool(choosable))
        self.design_name.setText(name)
        if pixmap is not None and not pixmap.isNull():
            self._design_pm = pixmap
        self.design.show()
        self._place_design()

    def hide_design(self):
        """촬영이 시작되면 접는다 — 찍는 순간엔 라이브뷰가 화면을 다 써야 한다."""
        self.design.hide()

    def _place_design(self):
        """좌측 디자인 그림을 지금 칸 크기에 맞춰 다시 그린다."""
        pm = self._design_pm
        if pm is None or pm.isNull() or not self.design.isVisible():
            return
        box = self.design_prev.size()
        if box.width() > 2 and box.height() > 2:
            self.design_prev.setPixmap(pm.scaled(box, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _place_cut_bar(self):
        self.cut_bar.adjustSize()
        m = 20
        self.cut_bar.move(max(0, self.live_page.width() - self.cut_bar.width() - m), m)
        self.cut_bar.raise_()

    def on_frame(self, qimage):
        if self.stack.currentIndex() != PAGE_LIVE:
            return                      # 준비/결과 화면일 땐 라이브 스케일링 낭비 안 함
        pm = QPixmap.fromImage(qimage)
        self.view.setPixmap(pm.scaled(self.view.size(), Qt.KeepAspectRatio, Qt.FastTransformation))

    # ── 컷 진행(한 장씩 채움) ──
    def set_shot_count(self, n: int):
        self.counter.setText(f"{n} / 4")
        for i, c in enumerate(self.cut_cells):
            if i >= n:
                c.clear(); c.setStyleSheet(CELL_EMPTY)

    def set_cut_thumbnail(self, idx: int, path: str):
        if 0 <= idx < len(self.cut_cells):
            cell = self.cut_cells[idx]
            pm = QPixmap(path)
            if not pm.isNull():
                cell.setPixmap(pm.scaled(cell.size(), Qt.KeepAspectRatioByExpanding,
                                         Qt.FastTransformation))
            cell.setStyleSheet(CELL_FULL)
        self.counter.setText(f"{idx + 1} / 4")
        self._place_cut_bar()

    def show_countdown(self, num: int):
        if num <= 0:
            self.countdown.hide(); return
        self.countdown.set_number(num)
        self.countdown.setGeometry(self.rect())
        self.countdown.show(); self.countdown.raise_()

    def flash(self):
        self.flash_ov.setGeometry(self.rect())
        self.flash_ov.show(); self.flash_ov.raise_()
        QTimer.singleShot(130, self.flash_ov.hide)

    def set_hint(self, text: str):
        self.hint.setText(text)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F11:
            self.toggle_fullscreen()
        elif e.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(e)
