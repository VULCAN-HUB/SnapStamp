"""색 선택 창 — 앱 톤에 맞춘 디자인.

기본 QColorDialog는 영문·시스템 룩이라 앱과 따로 논다. 자주 쓰는 색을 스와치로 크게
보여주고(운영자가 빠르게 고름), HEX 직접 입력과 '세밀 조정'(시스템 피커)도 함께 제공한다.
"""
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                             QPushButton, QLineEdit, QWidget, QColorDialog)
from ui.theme import INK, SURFACE, LINE, TEXT, MUTED, GOLD, HAIR, HAIR_HI, letter_spacing
from ui import icons

# 포토부스 프레임/문구에 자주 쓰는 색 — 무채색 · 파스텔 · 진한색 3줄
SWATCHES = [
    ["#FFFFFF", "#F5F2EC", "#EDEDED", "#C9C9C9", "#8A8A8A", "#4A4A4A", "#222222", "#000000"],
    ["#FFE9EC", "#FFD9C7", "#FFF3C4", "#DFF3E0", "#D6ECF7", "#E2DCF7", "#F7DCEF", "#EDE3D2"],
    ["#E5484D", "#FF7A29", "#F5C518", "#2FA84F", "#1F8FE0", "#4C7DFF", "#8B5CF6", "#E9C87A"],
]


def _eyebrow(t):
    lab = QLabel(t.upper())
    lab.setStyleSheet(f"color:{GOLD}; font-size:14px; font-weight:700;")
    letter_spacing(lab, 2.2)
    return lab


class ColorPickDialog(QDialog):
    def __init__(self, initial="#FFFFFF", parent=None, title="색 선택"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._color = QColor(initial if QColor(initial).isValid() else "#FFFFFF")
        self.setStyleSheet(f"QDialog{{background:{INK};}}")
        self.setMinimumWidth(460)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)

        head = QWidget(); head.setStyleSheet(f"background:{SURFACE}; border-bottom:1px solid {LINE};")
        hv = QVBoxLayout(head); hv.setContentsMargins(24, 16, 24, 14); hv.setSpacing(3)
        hv.addWidget(_eyebrow("색 선택"))
        t = QLabel(title); t.setStyleSheet(f"color:{TEXT}; font-size:23px; font-weight:800;")
        hv.addWidget(t)
        v.addWidget(head)

        body = QVBoxLayout(); body.setContentsMargins(24, 18, 24, 14); body.setSpacing(14)
        v.addLayout(body)

        # 현재 색 + HEX 입력
        row = QHBoxLayout(); row.setSpacing(12)
        self.chip = QLabel(); self.chip.setFixedSize(64, 44)
        row.addWidget(self.chip)
        self.hex = QLineEdit(self._color.name().upper())
        self.hex.setPlaceholderText("#RRGGBB")
        self.hex.textChanged.connect(self._on_hex)
        row.addWidget(self.hex, 1)
        adv = QPushButton("세밀 조정")
        adv.setToolTip("색상환에서 직접 고르기")
        adv.clicked.connect(self._advanced)
        row.addWidget(adv)
        body.addLayout(row)

        # 스와치
        body.addWidget(_eyebrow("자주 쓰는 색"))
        grid = QGridLayout(); grid.setSpacing(8)
        for r, line in enumerate(SWATCHES):
            for c, hexv in enumerate(line):
                b = QPushButton(); b.setFixedSize(44, 36); b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(hexv)
                b.setStyleSheet(
                    f"QPushButton{{background:{hexv}; border:1px solid {HAIR}; border-radius:8px;}}"
                    f"QPushButton:hover{{border:2px solid {GOLD};}}")
                b.clicked.connect(lambda _=False, h=hexv: self._set(h))
                grid.addWidget(b, r, c)
        body.addLayout(grid)

        foot = QWidget(); foot.setStyleSheet(f"background:{INK}; border-top:1px solid {LINE};")
        fr = QHBoxLayout(foot); fr.setContentsMargins(24, 12, 24, 14); fr.setSpacing(10)
        cancel = QPushButton("취소"); cancel.setMinimumHeight(44); cancel.clicked.connect(self.reject)
        ok = QPushButton("  적용"); ok.setObjectName("primary"); ok.setMinimumHeight(44)
        ok.setIcon(icons.icon("check", "#FFFFFF", 18)); ok.setIconSize(QSize(18, 18))
        ok.clicked.connect(self.accept)
        fr.addStretch(1); fr.addWidget(cancel); fr.addWidget(ok)
        v.addWidget(foot)
        self._paint_chip()

    def _paint_chip(self):
        self.chip.setStyleSheet(
            f"background:{self._color.name()}; border:1px solid {HAIR_HI}; border-radius:10px;")

    def _set(self, hexv):
        c = QColor(hexv)
        if c.isValid():
            self._color = c
            if self.hex.text().upper() != c.name().upper():
                self.hex.setText(c.name().upper())
            self._paint_chip()

    def _on_hex(self, txt):
        c = QColor(txt.strip())
        if c.isValid():
            self._color = c
            self._paint_chip()

    def _advanced(self):
        c = QColorDialog.getColor(self._color, self, "세밀 조정")
        if c.isValid():
            self._set(c.name())

    def color_name(self) -> str:
        return self._color.name().upper()

    @staticmethod
    def pick(initial, parent=None, title="색 선택"):
        """선택한 색(#RRGGBB) 반환, 취소면 None."""
        d = ColorPickDialog(initial, parent, title)
        try:
            from core.platform_utils import apply_dark_titlebar
            d.show(); apply_dark_titlebar(int(d.winId()))
        except Exception:  # noqa: BLE001
            pass
        return d.color_name() if d.exec_() == QDialog.Accepted else None
