"""Lucide SVG 아이콘 로더 — 텍스트 기호 대신 진짜 아이콘(단색 틴트).

Lucide(MIT) SVG는 stroke="currentColor" 를 쓴다. 원하는 색으로 치환해 QSvgRenderer 로
렌더 → QPixmap/QIcon. 번들(exe)·소스 양쪽에서 assets/icons/lucide 경로 해석.
"""
import sys
from pathlib import Path
from functools import lru_cache
from PyQt5.QtCore import Qt, QByteArray, QSize
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QColor
from PyQt5.QtSvg import QSvgRenderer


def _dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(".")
    return root / "assets" / "icons" / "lucide"


@lru_cache(maxsize=256)
def _svg_bytes(name: str, color: str, stroke: float) -> bytes:
    p = _dir() / f"{name}.svg"
    if not p.exists():
        return b""
    txt = p.read_text(encoding="utf-8")
    txt = txt.replace('stroke="currentColor"', f'stroke="{color}"')
    if stroke:
        txt = txt.replace('stroke-width="2"', f'stroke-width="{stroke}"')
    return txt.encode("utf-8")


def pixmap(name: str, color: str = "#EEF1F7", size: int = 20, stroke: float = 2.0) -> QPixmap:
    data = _svg_bytes(name, color, stroke)
    dpr = 2  # 레티나/고DPI 대비 2배 렌더 후 축소 → 선명
    pm = QPixmap(size * dpr, size * dpr)
    pm.fill(Qt.transparent)
    if data:
        r = QSvgRenderer(QByteArray(data))
        p = QPainter(pm)
        r.render(p)
        p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str = "#EEF1F7", size: int = 20, stroke: float = 2.0) -> QIcon:
    return QIcon(pixmap(name, color, size, stroke))
