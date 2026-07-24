"""대기(Attract) 화면 — 부스가 유휴일 때 손님을 끌어당기는 시네마틱 얼굴.

라이브 카메라를 세련된 프레임에 담아(지나가는 사람이 자기 모습을 봄) + 브랜드 모션 +
"트리거로 시작" CTA. 트리거 키/클릭으로 촬영 시작, 우상단 톱니로 운영자 설정 복귀.
"""
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QPixmap, QKeySequence
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
                             QSizePolicy, QGraphicsOpacityEffect)
from ui.theme import (INK, SURFACE, LINE, ACCENT, ACCENT_HI, TEXT, MUTED, GOLD,
                      HAIR, HAIR_HI, shadow, letter_spacing)
from ui import icons


class AttractWindow(QWidget):
    start_requested = pyqtSignal()
    setup_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.trigger_key = "Space"
        self.setStyleSheet(f"""
            AttractWindow {{ background:{INK}; }}
        """)
        h = QHBoxLayout(self); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)

        # ── 좌: 브랜드 + 히어로 카피 + CTA ──
        left = QWidget()
        left.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {INK}, stop:1 #0d1220);")
        lv = QVBoxLayout(left); lv.setContentsMargins(72, 60, 56, 60)
        brand = QHBoxLayout(); brand.setSpacing(12)
        dot = QLabel("●"); dot.setStyleSheet(f"color:{GOLD}; font-size:16px;")
        word = QLabel(f'<span style="color:{TEXT};">Snap</span>'
                      f'<span style="color:{ACCENT_HI};">Stamp</span>')
        word.setStyleSheet("font-size:28px; font-weight:800; letter-spacing:0.5px;")
        brand.addWidget(dot); brand.addWidget(word); brand.addStretch(1)
        lv.addLayout(brand)
        lv.addStretch(1)
        eyebrow = QLabel("LIFE IN FOUR CUTS")
        eyebrow.setStyleSheet(f"color:{GOLD}; font-size:17px; font-weight:700;")
        letter_spacing(eyebrow, 5.0)  # QSS는 자간 무시 → QFont로
        lv.addWidget(eyebrow)
        lv.addSpacing(14)
        hero = QLabel("다시 없을 이 순간,\n<span style='color:#8B94A7;'>네 컷.</span>")
        hero.setTextFormat(Qt.RichText)
        hero.setStyleSheet("color:#EEF1F7; font-size:66px; font-weight:800; line-height:105%;")
        lv.addWidget(hero)
        lv.addStretch(1)
        # CTA (은은하게 맥동)
        self.cta = QWidget()
        cl = QHBoxLayout(self.cta); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(16)
        self.key_pill = QLabel("스페이스바")
        # 키캡 스타일 — 미세 그라디언트 + 헤어라인(하드웨어 키처럼)
        self.key_pill.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {ACCENT_HI}, stop:1 {ACCENT});"
            "color:white; font-size:22px; font-weight:800;"
            "padding:14px 28px; border-radius:14px;"
            "border:1px solid rgba(255,255,255,0.25);")
        # ⚠️ 부모(cta)에 투명도 이펙트가 있어 자식에 또 그래픽 이펙트를 주면 중첩되어
        # 렌더링이 누락된다(Qt 제약). 알약 그림자는 생략하고 맥동만 사용.
        cta_txt = QLabel("를 눌러 시작하세요")
        cta_txt.setStyleSheet(f"color:{MUTED}; font-size:20px;")
        cl.addWidget(self.key_pill); cl.addWidget(cta_txt); cl.addStretch(1)
        lv.addWidget(self.cta)
        h.addWidget(left, 58)

        # ── 우: 라이브 카메라 프레임 ──
        right = QWidget()
        right.setStyleSheet(f"background:#0a0d15; border-left:1px solid {LINE};")
        rv = QVBoxLayout(right); rv.setContentsMargins(48, 48, 48, 48); rv.setSpacing(16)
        top = QHBoxLayout()
        self.live = QLabel("● LIVE")
        self.live.setStyleSheet(f"color:{MUTED}; font-size:16px; font-weight:700; letter-spacing:2px;")
        top.addWidget(self.live); top.addStretch(1)
        self.gear = QPushButton()
        self.gear.setIcon(icons.icon("settings", MUTED, 18)); self.gear.setIconSize(QSize(18, 18))
        self.gear.setFixedSize(40, 40)
        self.gear.setStyleSheet(
            f"QPushButton{{background:rgba(255,255,255,0.04);border:1px solid {HAIR};border-radius:12px;}}"
            f"QPushButton:hover{{border-color:{HAIR_HI};}}")
        self.gear.setToolTip("운영자 설정")
        self.gear.clicked.connect(self.setup_requested.emit)
        top.addWidget(self.gear)
        rv.addLayout(top)
        self.camframe = QWidget()
        self.camframe.setStyleSheet(
            f"background:#05070b; border:1px solid {LINE}; border-radius:16px;")
        shadow(self.camframe, blur=50, dy=16, alpha=170)
        cfl = QVBoxLayout(self.camframe); cfl.setContentsMargins(10, 10, 10, 10)
        self.view = QLabel("카메라를 준비하고 있어요…")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setStyleSheet(f"color:{MUTED}; font-size:20px; background:transparent;")
        self.view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.view.setMinimumSize(1, 1)
        cfl.addWidget(self.view)
        rv.addWidget(self.camframe, 1)
        h.addWidget(right, 42)

        # CTA 맥동 애니메이션
        self._eff = QGraphicsOpacityEffect(self.cta)
        self.cta.setGraphicsEffect(self._eff)
        self._anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim.setDuration(1300); self._anim.setStartValue(1.0); self._anim.setEndValue(0.55)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.setLoopCount(-1)

    def showEvent(self, e):
        self._anim.stop(); self._anim.setDirection(QPropertyAnimation.Forward)
        # 왕복 맥동: 끝나면 방향 반전
        try:
            self._anim.finished.disconnect()
        except Exception:
            pass
        self._anim.start()
        super().showEvent(e)

    def set_trigger(self, key):
        self.trigger_key = key or "Space"
        label = "스페이스바" if self.trigger_key == "Space" else self.trigger_key
        self.key_pill.setText(label)

    def on_frame(self, qimage):
        pm = QPixmap.fromImage(qimage)
        self.view.setPixmap(pm.scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.live.setStyleSheet(f"color:{ACCENT_HI}; font-size:16px; font-weight:700; letter-spacing:2px;")

    def mousePressEvent(self, e):
        # 클릭으로는 촬영을 시작하지 않는다(오탭 방지) — 오직 트리거 키로만 시작.
        super().mousePressEvent(e)

    def keyPressEvent(self, e):
        name = QKeySequence(e.key()).toString()
        if name and name == QKeySequence(self.trigger_key).toString() and not e.isAutoRepeat():
            self.start_requested.emit()
            return
        if e.key() == Qt.Key_Escape:
            self.setup_requested.emit()  # 운영자: 설정으로 복귀
            return
        super().keyPressEvent(e)
