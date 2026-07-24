from PyQt5.QtCore import QRect, QPoint, Qt
from PyQt5.QtGui import QPainter, QColor, QPixmap, QPen
from PyQt5.QtWidgets import QWidget

ACCENT = "#3D6BFF"
SNAP = 12  # 스냅 임계값(캔버스 좌표 px)


class SlotEditor(QWidget):
    """WYSIWYG 슬롯 배치 에디터. 캔버스(합성 결과 크기) 전체를 위젯에 맞춰
    letterbox로 보여주고(4컷 모두 보임), 드래그 시 캔버스/다른 슬롯 모서리에 스냅.
    전체 중심 스냅은 하지 않음 — 슬롯끼리·캔버스 모서리 정렬만.
    """

    def __init__(self, slots, canvas_size=(800, 600), parent=None):
        super().__init__(parent)
        self.canvas_w, self.canvas_h = canvas_size
        self.slots = [dict(s) for s in slots]
        self.template = None
        self._drag_idx = None
        self._drag_off = QPoint()
        self._mode = None   # "move" | "resize"
        self._guides = []   # [("v"|"h", 캔버스좌표)]
        self.setMinimumSize(320, 240)

    def set_template(self, path):
        self.template = QPixmap(path) if path else None
        self.update()

    def set_canvas_size(self, w, h):
        self.canvas_w, self.canvas_h = w, h
        self.update()

    def get_slots(self):
        return [dict(s) for s in self.slots]

    # ── 좌표 변환(캔버스 ↔ 위젯), letterbox ──
    def _fit(self):
        s = min(self.width() / self.canvas_w, self.height() / self.canvas_h)
        ox = (self.width() - self.canvas_w * s) / 2
        oy = (self.height() - self.canvas_h * s) / 2
        return ox, oy, s

    def _to_widget(self, x, y):
        ox, oy, s = self._fit()
        return int(ox + x * s), int(oy + y * s)

    def _to_canvas(self, px, py):
        ox, oy, s = self._fit()
        return (px - ox) / s, (py - oy) / s

    def paintEvent(self, _):
        p = QPainter(self)
        try:
            ox, oy, s = self._fit()
            cr = QRect(int(ox), int(oy), int(self.canvas_w * s), int(self.canvas_h * s))
            if self.template:
                p.drawPixmap(cr, self.template)
            else:
                p.fillRect(cr, QColor("#FFFFFF"))
            p.setPen(QColor("#3A4150")); p.drawRect(cr)
            # 슬롯 + 우하단 크기조절 핸들
            for sl in self.slots:
                x, y = self._to_widget(sl["x"], sl["y"])
                sw, sh = int(sl["w"] * s), int(sl["h"] * s)
                p.setPen(QPen(QColor(ACCENT), 2))
                p.drawRect(QRect(x, y, sw, sh))
                hs = 12
                p.fillRect(QRect(x + sw - hs, y + sh - hs, hs, hs), QColor(ACCENT))
            # 스냅 가이드(드래그 중)
            p.setPen(QPen(QColor("#7FA0FF"), 1, Qt.DashLine))
            for kind, val in self._guides:
                if kind == "v":
                    wx, _ = self._to_widget(val, 0)
                    p.drawLine(wx, cr.top(), wx, cr.bottom())
                else:
                    _, wy = self._to_widget(0, val)
                    p.drawLine(cr.left(), wy, cr.right(), wy)
        finally:
            p.end()

    def mousePressEvent(self, e):
        cx, cy = self._to_canvas(e.x(), e.y())
        _, _, s = self._fit()
        handle_px = 14 / s  # 위젯 14px를 캔버스 좌표로
        for i in range(len(self.slots) - 1, -1, -1):  # 위에 그려진 것부터
            sl = self.slots[i]
            # 우하단 핸들 근처면 크기조절
            brx, bry = sl["x"] + sl["w"], sl["y"] + sl["h"]
            if abs(cx - brx) <= handle_px and abs(cy - bry) <= handle_px:
                self._drag_idx = i; self._mode = "resize"
                self._ratio = sl["w"] / sl["h"] if sl["h"] else 1.0  # 비율 고정용
                return
            if QRect(sl["x"], sl["y"], sl["w"], sl["h"]).contains(int(cx), int(cy)):
                self._drag_idx = i; self._mode = "move"
                self._drag_off = QPoint(int(cx - sl["x"]), int(cy - sl["y"]))
                return

    def mouseMoveEvent(self, e):
        if self._drag_idx is None:
            return
        cx, cy = self._to_canvas(e.x(), e.y())
        sl = self.slots[self._drag_idx]
        if self._mode == "resize":
            # 비율 고정: 커서까지 폭을 기준으로 하되, 캔버스 밖으로 안 나가게 높이로도 제한
            nw = max(60, cx - sl["x"])
            nh = nw / self._ratio
            if sl["x"] + nw > self.canvas_w:
                nw = self.canvas_w - sl["x"]; nh = nw / self._ratio
            if sl["y"] + nh > self.canvas_h:
                nh = self.canvas_h - sl["y"]; nw = nh * self._ratio
            sl["w"], sl["h"] = int(round(nw)), int(round(nh))
        else:
            nx = cx - self._drag_off.x()
            ny = cy - self._drag_off.y()
            nx, ny, self._guides = self._snap(self._drag_idx, nx, ny, sl["w"], sl["h"])
            nx = max(0, min(nx, self.canvas_w - sl["w"]))
            ny = max(0, min(ny, self.canvas_h - sl["h"]))
            sl["x"], sl["y"] = int(round(nx)), int(round(ny))
        self.update()

    def mouseReleaseEvent(self, _):
        self._drag_idx = None
        self._mode = None
        self._guides = []
        self.update()

    def _snap(self, idx, x, y, w, h):
        # 스냅 후보: 캔버스 좌/우/상/하 + 다른 슬롯의 좌맞춤/우맞춤/인접(붙이기)
        candX = [(0, 0), (self.canvas_w - w, self.canvas_w)]  # (슬롯x값, 가이드선 캔버스x)
        candY = [(0, 0), (self.canvas_h - h, self.canvas_h)]
        for j, o in enumerate(self.slots):
            if j == idx:
                continue
            candX += [(o["x"], o["x"]), (o["x"] + o["w"] - w, o["x"] + o["w"]),
                      (o["x"] + o["w"], o["x"] + o["w"]), (o["x"] - w, o["x"])]
            candY += [(o["y"], o["y"]), (o["y"] + o["h"] - h, o["y"] + o["h"]),
                      (o["y"] + o["h"], o["y"] + o["h"]), (o["y"] - h, o["y"])]
        guides = []
        for val, guide in candX:
            if abs(x - val) <= SNAP:
                x = val; guides.append(("v", guide)); break
        for val, guide in candY:
            if abs(y - val) <= SNAP:
                y = val; guides.append(("h", guide)); break
        return x, y, guides
