"""보조 모니터용 관객 화면 — 라이브뷰 + 카운트다운 + 플래시를 계속 미러링.

메인(운영자) 창과 별개의 최상위 창이다. 카메라 라이브 프레임을 항상 보여줘서
피사체가 자기 모습을 보며 촬영할 수 있게 한다. 촬영 카운트다운·플래시도 크게 표시.
전체화면/창모드 토글(F11) 및 자유 이동(창모드) 가능.
"""
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from ui.theme import TEXT, MUTED, ACCENT
from ui.shoot_window import CountdownRing, _ColorOverlay


class AudienceWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("SnapStamp — 관객 화면")
        self.setStyleSheet("background:#000000;")
        self.resize(960, 600)
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.view = QLabel(); self.view.setAlignment(Qt.AlignCenter)
        self.view.setText("카메라 대기 중…")
        self.view.setStyleSheet(f"color:{MUTED}; font-size:30px; background:#000000;")
        self.view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.view.setMinimumSize(1, 1)
        root.addWidget(self.view, 1)

        self.hint = QLabel("곧 촬영을 시작합니다 📸")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet(
            f"color:white; font-size:32px; font-weight:bold; background:{ACCENT}; padding:20px;")
        root.addWidget(self.hint)

        self.countdown = CountdownRing(self); self.countdown.hide()
        self.flash_ov = _ColorOverlay("white", self)  # 직접 칠 → 항상 흰 플래시
        self.flash_ov.hide()

    def resizeEvent(self, e):
        self.countdown.setGeometry(self.rect())
        self.flash_ov.setGeometry(self.rect())
        super().resizeEvent(e)

    def on_frame(self, qimage):
        pm = QPixmap.fromImage(qimage)
        self.view.setPixmap(pm.scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

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
