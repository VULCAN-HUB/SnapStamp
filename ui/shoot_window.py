from PyQt5.QtCore import (Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve,
                          QRectF)
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QFont
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QSizePolicy, QPushButton, QGraphicsOpacityEffect)
from ui.theme import ACCENT, TEXT, MUTED, INK, SURFACE

CELL_EMPTY = "border:2px solid #333A45; border-radius:6px; background:#0A0D12;"
CELL_FULL = f"border:2px solid {ACCENT}; border-radius:6px; background:#12203F;"


class _ColorOverlay(QWidget):
    """단색으로 '항상' 칠해지는 오버레이. 전역 스타일시트(QWidget{background:...})나
    팔레트 설정은 상황에 따라 무시되어 배경이 안 그려질 때가 있다(플래시 랜덤 미표시 원인).
    paintEvent 에서 직접 fillRect 하면 무조건 칠해진다."""
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self._c = QColor(color)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), self._c)
        p.end()


class CountdownRing(QWidget):
    """전체화면 카운트다운 오버레이 — 은은한 배경 + 코발트 링 + 큰 숫자."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.number = 0

    def set_number(self, n):
        self.number = n
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(8, 10, 14, 165))  # 은은한 어두운 배경
        cx, cy = self.width() / 2, self.height() / 2
        r = min(self.width(), self.height()) * 0.20
        ring = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        # 은은한 외곽 글로우
        p.setPen(QPen(QColor(61, 107, 255, 60), 18))
        p.drawEllipse(ring)
        # 링
        p.setPen(QPen(QColor(ACCENT), 8))
        p.drawEllipse(ring)
        # 숫자
        f = QFont(); f.setPixelSize(int(r * 1.3)); f.setBold(True)
        p.setFont(f); p.setPen(QColor(255, 255, 255))
        p.drawText(ring, Qt.AlignCenter, str(self.number))
        p.end()


class ShootWindow(QWidget):
    home_requested = pyqtSignal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.shot_count = 0
        # ⚠️ 이게 없으면 setFocus()가 무효라 키보드 포커스가 붕 뜨고,
        #    트리거 단축키(Space)가 전달되지 않아 손님이 촬영을 시작할 수 없다.
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("background:#000000;")
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── 상단 바 ──
        top = QWidget(); top.setStyleSheet("background:rgba(0,0,0,0.55);")
        tl = QHBoxLayout(top); tl.setContentsMargins(28, 14, 28, 14)
        self.counter = QLabel("0 / 4")
        self.counter.setStyleSheet(f"color:{TEXT}; font-size:30px; font-weight:bold;")
        home = QPushButton("↺")  # 운영자용 — 작고 은은하게(손님 오조작 방지)
        home.setFixedSize(34, 34)
        home.setStyleSheet(f"QPushButton{{background:transparent;border:1px solid #2A303A;"
                           f"border-radius:17px;color:{MUTED};font-size:17px;padding:0;}}"
                           f"QPushButton:hover{{border-color:{ACCENT};color:{ACCENT};}}")
        home.setFocusPolicy(Qt.NoFocus)   # Space가 이 버튼을 누르는 오작동 방지
        home.clicked.connect(self.home_requested.emit)
        tl.addWidget(self.counter); tl.addSpacing(16); tl.addWidget(home); tl.addStretch(1)
        self.cut_cells = []
        for _ in range(4):
            c = QLabel(); c.setFixedSize(96, 72); c.setStyleSheet(CELL_EMPTY)
            self.cut_cells.append(c); tl.addWidget(c)
        root.addWidget(top)

        # ── 중앙: 준비 단계엔 좌=고른 디자인 / 우=라이브뷰, 촬영 시작하면 라이브뷰가 전부 ──
        split = QHBoxLayout(); split.setContentsMargins(0, 0, 0, 0); split.setSpacing(0)
        root.addLayout(split, 1)
        self.design = QWidget()
        self.design.setStyleSheet("background:#0A0D12; border-right:1px solid #222831;")
        dv = QVBoxLayout(self.design); dv.setContentsMargins(20, 16, 20, 16); dv.setSpacing(10)
        self.design_name = QLabel("디자인")
        self.design_name.setAlignment(Qt.AlignCenter)
        self.design_name.setStyleSheet(f"color:{TEXT}; font-size:26px; font-weight:bold;")
        dv.addWidget(self.design_name)
        self.design_prev = QLabel()
        self.design_prev.setAlignment(Qt.AlignCenter)
        self.design_prev.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.design_prev.setMinimumSize(1, 1)
        dv.addWidget(self.design_prev, 1)
        self.design_tip = QLabel("◀ ▶ 로 디자인 고르기")
        self.design_tip.setAlignment(Qt.AlignCenter)
        self.design_tip.setStyleSheet("color:#FFD98A; font-size:20px; font-weight:bold;")
        dv.addWidget(self.design_tip)
        self.design.hide()
        self._design_pm = None
        split.addWidget(self.design, 4)

        self.view = QLabel(); self.view.setAlignment(Qt.AlignCenter)
        self.view.setText("카메라 연결 대기 중…")
        self.view.setStyleSheet(f"color:{MUTED}; font-size:28px; background:#000000;")
        self.view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.view.setMinimumSize(1, 1)
        split.addWidget(self.view, 6)

        # ── 하단 안내 바 ── 어떤 모니터 비율에서도 일정하고 넉넉한 높이(비율 무관 고정)
        self.hint = QLabel("버튼을 눌러 촬영을 시작하세요")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setMinimumHeight(92)
        self.hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.hint.setStyleSheet(
            f"color:white; font-size:29px; font-weight:bold; background:{ACCENT}; padding:0 24px;")
        root.addWidget(self.hint)

        # ── 하단 경고 바 ── 준비 화면 방치 시 "N초 뒤 처음으로 돌아갑니다" 예고(놀람 방지)
        self.warn = QLabel("")
        self.warn.setAlignment(Qt.AlignCenter)
        self.warn.setMinimumHeight(56)
        self.warn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.warn.setStyleSheet(
            "color:#FFD98A; font-size:25px; font-weight:bold; background:#3A2E12; padding:0 20px;")
        self.warn.hide()
        root.addWidget(self.warn)

        # ── 카운트다운 오버레이(링 + 숫자, 팝 애니메이션) ──
        self.countdown = CountdownRing(self)
        self.countdown.hide()
        self._cd_eff = QGraphicsOpacityEffect(self.countdown)
        self.countdown.setGraphicsEffect(self._cd_eff)
        self._cd_anim = QPropertyAnimation(self._cd_eff, b"opacity", self)
        self._cd_anim.setDuration(260); self._cd_anim.setStartValue(0.0)
        self._cd_anim.setEndValue(1.0); self._cd_anim.setEasingCurve(QEasingCurve.OutBack)

        # ── 셔터 플래시(흰 오버레이) ── paintEvent 직접 칠 → '항상' 터짐(랜덤 미표시 해결)
        self.flash_ov = _ColorOverlay("white", self)
        self.flash_ov.hide()

        # ── 합성 대기 오버레이 ── 배경도 직접 칠(스타일시트 오버라이드에 안 흔들림)
        self.busy = _ColorOverlay(INK, self)
        bl = QVBoxLayout(self.busy); bl.setAlignment(Qt.AlignCenter); bl.setSpacing(24)
        self.busy_title = QLabel("✨ 사진을 만들고 있어요")
        self.busy_title.setAlignment(Qt.AlignCenter)
        self.busy_title.setStyleSheet(f"color:{TEXT}; font-size:42px; font-weight:bold;")
        bl.addWidget(self.busy_title)
        self.busy_dots = QLabel("●")
        self.busy_dots.setAlignment(Qt.AlignCenter)
        self.busy_dots.setStyleSheet(f"color:{ACCENT}; font-size:32px;")
        bl.addWidget(self.busy_dots)
        self.busy.hide()
        self._busy_timer = QTimer(self)
        self._busy_timer.timeout.connect(self._spin)
        self._spin_n = 0

        # ⚠️ 트리거 키는 이 위젯이 직접 받지 않는다 — QShortcut(WindowShortcut)도,
        #    창 포커스도 이 구조(QStackedWidget 전체화면 + 보조 모니터 창)에서는 못 받는다.
        #    main.py 의 앱 전역 키 라우터가 현재 화면을 보고 controller.on_trigger() 를 부른다.

    def resizeEvent(self, e):
        self._place_design()
        self.countdown.setGeometry(self.rect())
        self.flash_ov.setGeometry(self.rect())
        self.busy.setGeometry(self.rect())
        super().resizeEvent(e)

    def on_frame(self, qimage):
        # ⚠️ 라이브뷰는 매 프레임 스케일된다. 1080p에 SmoothTransformation을 쓰면 비용이 커
        #    카운트다운·플래시 때 끊김이 생긴다. 움직이는 영상은 Fast로 충분.
        if not self.isVisible():
            return
        pm = QPixmap.fromImage(qimage)
        self.view.setPixmap(pm.scaled(self.view.size(), Qt.KeepAspectRatio, Qt.FastTransformation))

    def set_shot_count(self, n: int):
        self.shot_count = n
        self.counter.setText(f"{n} / 4")
        for i, c in enumerate(self.cut_cells):
            c.setStyleSheet(CELL_FULL if i < n else CELL_EMPTY)
        if n == 0:
            for c in self.cut_cells:
                c.clear(); c.setStyleSheet(CELL_EMPTY)
            self.hide_busy()

    def set_cut_thumbnail(self, idx: int, path: str):
        if 0 <= idx < len(self.cut_cells):
            cell = self.cut_cells[idx]
            pm = QPixmap(path)
            if not pm.isNull():
                cell.setPixmap(pm.scaled(cell.size(), Qt.KeepAspectRatioByExpanding,
                                         Qt.FastTransformation))
            cell.setStyleSheet(CELL_FULL)

    def show_countdown(self, num: int):
        if num <= 0:
            self.countdown.hide(); return
        self.countdown.set_number(num)
        self.countdown.setGeometry(self.rect())
        self.countdown.show(); self.countdown.raise_()
        # ⚠️ 여기서 QGraphicsOpacityEffect 페이드를 돌리면 전체화면 오버레이가 매 프레임
        #    오프스크린 재합성되어 카운트다운이 끊긴다. 즉시 표시가 더 또렷하고 가볍다.

    def flash(self):
        """셔터 플래시: 흰 화면 잠깐."""
        self.flash_ov.setGeometry(self.rect())
        self.flash_ov.show(); self.flash_ov.raise_()
        QTimer.singleShot(130, self.flash_ov.hide)

    def show_busy(self):
        """합성 대기 화면(얼어붙은 라이브뷰 대신)."""
        self.busy.setGeometry(self.rect())
        self.busy.show(); self.busy.raise_()
        self._spin_n = 0
        self._busy_timer.start(280)

    def hide_busy(self):
        self.busy.hide()
        self._busy_timer.stop()

    def _spin(self):
        self._spin_n = (self._spin_n + 1) % 4
        self.busy_dots.setText("●" * (self._spin_n + 1))

    def set_design(self, name: str, pixmap=None, choosable: bool = True):
        """준비 단계에 고른 디자인을 좌측에 보여준다(운영자도 무엇이 선택됐는지 봐야 한다)."""
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
        self.design.hide()

    def _place_design(self):
        pm = self._design_pm
        if pm is None or pm.isNull() or not self.design.isVisible():
            return
        box = self.design_prev.size()
        if box.width() > 2 and box.height() > 2:
            self.design_prev.setPixmap(pm.scaled(box, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_hint(self, text: str):
        self.hint.setText(text)

    def set_warning(self, text: str):
        """하단 경고 바. 빈 문자열이면 숨김."""
        if text:
            self.warn.setText(text)
            self.warn.show()
        else:
            self.warn.hide()

