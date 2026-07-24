"""브랜드 테마 — 컴퍼니 'A·Signal' 디자인 리서치 적용(Dribbble·Awwwards 근거):
중립 쿨 잉크 배경 + 단일 강조색(코발트), 큰 타이포, 둥근 카드, 절제된 모션.
About은 [[brand-common-design]] 요구(Unknown/2026/@unknown8563) 유지.
"""
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase, QPixmap, QColor, QFont
from PyQt5.QtWidgets import (QWidget, QLabel, QDialog, QHBoxLayout, QVBoxLayout,
                             QPushButton, QGraphicsDropShadowEffect, QSpinBox, QComboBox,
                             QSlider)
import version
from core.platform_utils import platform_label


def shadow(widget, blur=26, dy=8, alpha=80):
    """부드러운 그림자(깊이감). 다크에선 깊이의 주역은 헤어라인 보더 + 명도 사다리이고,
    그림자는 떠 있는 요소(어트랙트 카메라·결과 카드)에만 은은하게 보조로 쓴다."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)
    return eff


class NoWheelSpinBox(QSpinBox):
    """마우스 휠로 값이 바뀌지 않는 숫자 입력.
    ⚠️ 설정 창이 스크롤 영역이라, 기본 QSpinBox는 스크롤하다 위를 지나가면 값이 바뀐다.
    휠 이벤트를 ignore 해서 값은 그대로 두고 부모(스크롤 영역)가 스크롤되게 한다."""
    def wheelEvent(self, e):
        e.ignore()


class NoWheelComboBox(QComboBox):
    """마우스 휠로 선택이 바뀌지 않는 콤보박스(위와 같은 이유)."""
    def wheelEvent(self, e):
        e.ignore()


class NoWheelSlider(QSlider):
    """가로 슬라이더 — 드래그로만 조절(휠 오조작 방지)."""
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)

    def wheelEvent(self, e):
        e.ignore()


def letter_spacing(widget, px: float):
    """자간 적용. ⚠️ Qt QSS는 letter-spacing 을 무시하므로 QFont 로만 적용된다."""
    f = widget.font()
    f.setLetterSpacing(QFont.AbsoluteSpacing, px)
    widget.setFont(f)
    return widget

# 프리미엄 다크 팔레트 — 시네마틱 잉크 + 코발트(인터랙션) + 샴페인 골드(프리미엄 시그널)
INK = "#0B0E13"        # 배경(깊은 차가운 근-검정)
SURFACE = "#141A24"    # 카드/패널
SURFACE2 = "#1C232F"   # 입력/셀
LINE = "#283040"       # 라인
TEXT = "#EEF1F7"       # 본문
MUTED = "#8B94A7"      # 보조(슬레이트)
ELEV = "#222B3A"       # 중첩/호버 표면(명도 사다리 상단)
ACCENT = "#4C7DFF"     # 코발트 — CTA·활성·강조에만
ACCENT_HI = "#6E97FF"
GOLD = "#E9C87A"       # 샴페인 골드 — 프리미엄 악센트(브랜드 점·미세 하이라이트)
GOLD_DIM = "rgba(233,200,122,0.22)"  # 골드 하어라인
OK_GREEN = "#46D08A"   # 연결/정상
# 헤어라인 — 다크 프리미엄의 깊이 표현(드롭섀도우 대신). 흰색 알파.
HAIR = "rgba(255,255,255,0.08)"
HAIR_HI = "rgba(255,255,255,0.16)"
YOUTUBE = "@unknown8563"

# 통일 폰트 — Pretendard(번들) 우선. 전 화면 일관 = 싼티 제거의 핵심.
WORDMARK_FF = "'Pretendard','Segoe UI',sans-serif"
BODY_FF = "'Pretendard','Malgun Gothic','Apple SD Gothic Neo','Segoe UI',sans-serif"


def _assets_dir() -> Path:
    """번들(exe) 또는 소스 실행 양쪽에서 assets 경로 해석."""
    import sys
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "assets"
    return Path("assets")


_FONTS_LOADED = False


def load_fonts():
    global _FONTS_LOADED
    if _FONTS_LOADED:
        return
    d = _assets_dir() / "fonts"
    if d.exists():
        for f in sorted(d.glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(f))
    _FONTS_LOADED = True


def apply_app_style(app):
    """전역 스타일 — 큰 기본 글자(16px)와 일관된 다크 UI."""
    load_fonts()
    app.setStyleSheet(f"""
        QWidget {{ background:{INK}; color:{TEXT}; font-family:{BODY_FF}; font-size:19px; }}
        QLabel {{ color:{TEXT}; background:transparent; }}
        QPushButton {{
            background:rgba(255,255,255,0.045); color:{TEXT}; border:1px solid {HAIR};
            border-radius:11px; padding:11px 18px; font-size:18px; font-weight:600;
        }}
        QPushButton:hover {{ border-color:{HAIR_HI}; background:rgba(255,255,255,0.08); }}
        QPushButton:pressed {{ background:rgba(255,255,255,0.03); }}
        QPushButton#primary {{ background:{ACCENT}; color:white; border:none;
            font-weight:700; font-size:22px; border-radius:12px; padding:14px 26px; }}
        QPushButton#primary:hover {{ background:{ACCENT_HI}; color:white; }}
        QPushButton#primary:disabled {{ background:#26314D; color:#7C89A8; }}
        QSpinBox, QComboBox, QLineEdit {{
            background:{SURFACE2}; color:{TEXT}; border:1px solid {HAIR};
            border-radius:10px; padding:11px 13px; font-size:19px; min-height:26px;
        }}
        QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color:{HAIR_HI}; }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border:1px solid {ACCENT}; }}
        QComboBox::drop-down {{ border:none; width:28px; }}
        QComboBox QAbstractItemView {{ background:{SURFACE}; color:{TEXT}; outline:none;
            border:1px solid {HAIR_HI}; selection-background-color:{ACCENT}; font-size:18px; padding:4px; }}
        QSpinBox::up-button, QSpinBox::down-button {{ width:22px; background:transparent; border:none; }}
        QSlider::groove:horizontal {{ height:6px; background:{SURFACE2};
            border:1px solid {HAIR}; border-radius:3px; }}
        QSlider::sub-page:horizontal {{ background:{ACCENT}; border-radius:3px; }}
        QSlider::handle:horizontal {{ background:{TEXT}; width:18px; height:18px;
            margin:-7px 0; border-radius:9px; }}
        QSlider::handle:horizontal:hover {{ background:white; }}
        QToolTip {{ background:#0F141C; color:{TEXT}; border:1px solid {HAIR_HI}; padding:6px 9px; }}
    """)


def make_header(parent) -> QWidget:
    bar = QWidget(parent); bar.setObjectName("header"); bar.setFixedHeight(64)
    bar.setStyleSheet(f"#header {{ background:{INK}; border-bottom:1px solid {LINE}; }}")
    lay = QHBoxLayout(bar); lay.setContentsMargins(24, 0, 20, 0); lay.setSpacing(14)
    logo = QLabel()
    ico = Path("assets/snapstamp.png")
    if ico.exists():
        logo.setPixmap(QPixmap(str(ico)).scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    lay.addWidget(logo)
    word = QLabel(f'<span style="color:{TEXT};">Snap</span>'
                  f'<span style="color:{ACCENT};">Stamp</span>')
    word.setStyleSheet(f"font-family:{WORDMARK_FF}; font-size:32px; font-weight:bold;")
    letter_spacing(word, 0.3)
    lay.addWidget(word)
    tag = QLabel("EVENT PHOTOBOOTH")
    tag.setStyleSheet(f"color:{MUTED}; font-size:14px; font-weight:600; padding-top:9px;")
    letter_spacing(tag, 2.0)
    lay.addWidget(tag)
    lay.addStretch(1)
    credit = QLabel("PROJECT 04  ·  UNKNOWN")
    credit.setStyleSheet(f"color:{MUTED}; font-size:14px;")
    letter_spacing(credit, 1.2)
    lay.addWidget(credit)
    from ui import icons
    btn = QPushButton(); btn.setFixedSize(34, 34)
    btn.setIcon(icons.icon("settings", MUTED, 17)); btn.setToolTip("정보")
    btn.setStyleSheet(f"QPushButton {{ border:1px solid {HAIR}; border-radius:10px; "
                      f"background:rgba(255,255,255,0.04); }} QPushButton:hover {{ border-color:{HAIR_HI}; }}")
    btn.clicked.connect(lambda: show_about(parent).exec_())
    lay.addWidget(btn)
    # 항상 보이는 안전 종료 버튼(우측 상단). 사용하는 화면에서 .quit_btn 에 연결.
    qbtn = QPushButton("  종료"); qbtn.setFixedHeight(38)
    qbtn.setIcon(icons.icon("x", "#FF8A9B", 16))
    qbtn.setStyleSheet("QPushButton { background:#3A1D22; border:1px solid #7A2E38; "
                       "border-radius:10px; color:#FF8A9B; padding:0 16px; font-size:17px; "
                       "font-weight:600; } QPushButton:hover { background:#5A2530; color:white; }")
    lay.addWidget(qbtn)
    bar.quit_btn = qbtn
    return bar


def show_about(parent) -> QDialog:
    dlg = QDialog(parent); dlg.setWindowTitle("About SnapStamp"); dlg.setFixedWidth(420)
    dlg.setStyleSheet(f"background:{INK};")
    v = QVBoxLayout(dlg); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
    banner = QLabel("SnapStamp\n이벤트 포토부스")
    banner.setStyleSheet(
        f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2A4BC0,stop:1 {ACCENT});"
        f"color:white; padding:22px 24px; font-size:24px; font-weight:bold;")
    v.addWidget(banner)
    body = QVBoxLayout(); body.setContentsMargins(24, 18, 24, 10); body.setSpacing(10)
    for label, value in [("제작", "Unknown"), ("연도", "2026"), ("버전", version.RELEASE_LABEL),
                         ("유튜브", YOUTUBE), ("엔진", "PyQt5 · OpenCV · Pillow · qrcode"),
                         ("플랫폼", platform_label())]:
        row = QHBoxLayout()
        lab = QLabel(label); lab.setFixedWidth(64); lab.setStyleSheet(f"color:{MUTED}; font-size:15px;")
        val = QLabel(value)
        val.setStyleSheet(f"color:{ACCENT if label=='유튜브' else TEXT}; font-size:17px; font-weight:bold;")
        row.addWidget(lab); row.addWidget(val); row.addStretch(1); body.addLayout(row)
    v.addLayout(body)
    barbtn = QHBoxLayout(); barbtn.setContentsMargins(24, 10, 24, 18); barbtn.addStretch(1)
    ok = QPushButton("확인"); ok.setObjectName("primary"); ok.clicked.connect(dlg.accept)
    barbtn.addWidget(ok); v.addLayout(barbtn)
    return dlg
