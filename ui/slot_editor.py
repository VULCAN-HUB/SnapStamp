from PyQt5.QtCore import QRect, QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPixmap, QPen
from PyQt5.QtWidgets import QWidget

ACCENT = "#3D6BFF"
ACCENT_SEL = "#7FA0FF"   # 선택된 슬롯 강조
SNAP = 12  # 스냅 임계값(캔버스 좌표 px)


class SlotEditor(QWidget):
    """WYSIWYG 슬롯 배치 에디터. 캔버스(합성 결과 크기) 전체를 위젯에 맞춰
    letterbox로 보여주고(모든 컷 보임), 드래그 시 캔버스/다른 슬롯 모서리에 스냅.

    편의 기능:
    - 클릭하면 슬롯이 '선택'되어 유지된다(파란 굵은 테두리).
    - 선택 후 방향키로 1px씩(Shift=10px) 미세 이동.
    - **균등 배치(even) 온/오프**: 켜면 모든 칸이 하나의 격자처럼 묶여
      · 한 칸을 드래그하면 전체가 같이 이동
      · 한 칸의 크기를 바꾸면 전체가 같은 크기로 함께 조절(간격 유지)
    """
    changed = pyqtSignal()   # 슬롯이 바뀔 때 — 설정 화면이 갱신

    def __init__(self, slots, canvas_size=(800, 600), parent=None):
        super().__init__(parent)
        self.canvas_w, self.canvas_h = canvas_size
        self.slots = [dict(s) for s in slots]
        self.template = None
        self._drag_idx = None
        self._drag_off = QPoint()
        self._mode = None   # "move" | "resize"
        self._guides = []
        self.sel = None
        self.even = False           # 균등 배치 모드
        self._grid = None           # even 모드일 때 격자 파라미터
        self._cells = []            # 각 슬롯의 (열, 행)
        self.setMinimumSize(320, 240)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_template(self, path):
        self.template = QPixmap(path) if path else None
        self.update()

    def set_canvas_size(self, w, h):
        self.canvas_w, self.canvas_h = w, h
        if self.even:
            self._capture_grid(normalize=False)
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
                scaled = self.template.scaled(cr.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                dx = cr.x() + (cr.width() - scaled.width()) // 2
                dy = cr.y() + (cr.height() - scaled.height()) // 2
                p.drawPixmap(dx, dy, scaled)
            else:
                p.fillRect(cr, QColor("#FFFFFF"))
            p.setPen(QColor("#3A4150")); p.drawRect(cr)
            for i, sl in enumerate(self.slots):
                x, y = self._to_widget(sl["x"], sl["y"])
                sw, sh = int(sl["w"] * s), int(sl["h"] * s)
                selected = (i == self.sel)
                col = QColor(ACCENT_SEL if selected else ACCENT)
                p.setPen(QPen(col, 3 if selected else 2))
                p.drawRect(QRect(x, y, sw, sh))
                p.setPen(col)
                p.drawText(QRect(x, y, sw, sh), Qt.AlignCenter, str(i + 1))
                hs = 12
                p.fillRect(QRect(x + sw - hs, y + sh - hs, hs, hs), col)
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
        self.setFocus()
        cx, cy = self._to_canvas(e.x(), e.y())
        _, _, s = self._fit()
        handle_px = 14 / s
        for i in range(len(self.slots) - 1, -1, -1):
            sl = self.slots[i]
            brx, bry = sl["x"] + sl["w"], sl["y"] + sl["h"]
            if abs(cx - brx) <= handle_px and abs(cy - bry) <= handle_px:
                self._drag_idx = i; self._mode = "resize"; self.sel = i
                self._ratio = sl["w"] / sl["h"] if sl["h"] else 1.0
                self.update()
                return
            if QRect(sl["x"], sl["y"], sl["w"], sl["h"]).contains(int(cx), int(cy)):
                self._drag_idx = i; self._mode = "move"; self.sel = i
                self._drag_off = QPoint(int(cx - sl["x"]), int(cy - sl["y"]))
                self.update()
                return
        self.sel = None
        self.update()

    def mouseMoveEvent(self, e):
        if self._drag_idx is None:
            return
        cx, cy = self._to_canvas(e.x(), e.y())
        sl = self.slots[self._drag_idx]
        if self.even and self._grid:
            self._drag_even(self._drag_idx, cx, cy)
        elif self._mode == "resize":
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
        was = self._drag_idx is not None
        self._drag_idx = None
        self._mode = None
        self._guides = []
        self.update()
        if was:
            self.changed.emit()

    def keyPressEvent(self, e):
        if self.sel is None or not (0 <= self.sel < len(self.slots)):
            super().keyPressEvent(e); return
        step = 10 if (e.modifiers() & Qt.ShiftModifier) else 1
        dx = dy = 0
        k = e.key()
        if k == Qt.Key_Left:
            dx = -step
        elif k == Qt.Key_Right:
            dx = step
        elif k == Qt.Key_Up:
            dy = -step
        elif k == Qt.Key_Down:
            dy = step
        else:
            super().keyPressEvent(e); return
        if self.even and self._grid:
            # 균등 모드: 전체 격자를 함께 이동
            g = self._grid
            g["x0"] = max(0, min(g["x0"] + dx, self.canvas_w - self._grid_w()))
            g["y0"] = max(0, min(g["y0"] + dy, self.canvas_h - self._grid_h()))
            self._rebuild_from_grid()
        else:
            sl = self.slots[self.sel]
            sl["x"] = int(max(0, min(sl["x"] + dx, self.canvas_w - sl["w"])))
            sl["y"] = int(max(0, min(sl["y"] + dy, self.canvas_h - sl["h"])))
        self.update()
        self.changed.emit()

    # ── 균등 배치(even) 모드 ────────────────────────────────────────────
    def set_even(self, on: bool, normalize: bool = True):
        """균등 모드 켜기/끄기. 켤 때 normalize=True면 즉시 같은 크기·간격으로 정렬."""
        self.even = bool(on)
        if self.even:
            if normalize:
                self.distribute_evenly()
            self._capture_grid(normalize=False)
        else:
            self._grid = None
        self.update()

    def _grid_w(self):
        g = self._grid
        return (g["cols"] - 1) * (g["w"] + g["gx"]) + g["w"]

    def _grid_h(self):
        g = self._grid
        return (g["rows"] - 1) * (g["h"] + g["gy"]) + g["h"]

    def _capture_grid(self, normalize=True):
        """현재 슬롯에서 격자 파라미터(열·행·크기·간격·좌상단)를 추출해 저장."""
        n = len(self.slots)
        if n == 0:
            self._grid = None; return
        if normalize:
            self.distribute_evenly()
        ws = sorted(s["w"] for s in self.slots)
        hs = sorted(s["h"] for s in self.slots)
        w, h = ws[n // 2], hs[n // 2]
        cxs = [s["x"] + s["w"] / 2 for s in self.slots]
        cys = [s["y"] + s["h"] / 2 for s in self.slots]
        col_rank, ncols = self._ranks(cxs, max(1, w) * 0.5)
        row_rank, nrows = self._ranks(cys, max(1, h) * 0.5)
        self._cells = list(zip(col_rank, row_rank))
        # 열/행 대표 좌표(좌상단)
        col_x = {}; row_y = {}
        for i, s in enumerate(self.slots):
            col_x.setdefault(col_rank[i], []).append(s["x"])
            row_y.setdefault(row_rank[i], []).append(s["y"])
        xs = [sum(v) / len(v) for _, v in sorted(col_x.items())]
        ys = [sum(v) / len(v) for _, v in sorted(row_y.items())]
        x0 = int(round(min(xs))); y0 = int(round(min(ys)))
        gx = int(round((xs[1] - xs[0]) - w)) if ncols > 1 else max(8, int(w * 0.12))
        gy = int(round((ys[1] - ys[0]) - h)) if nrows > 1 else max(8, int(h * 0.12))
        gx = max(0, gx); gy = max(0, gy)
        self._grid = {"cols": ncols, "rows": nrows, "w": w, "h": h,
                      "gx": gx, "gy": gy, "x0": x0, "y0": y0}
        self._rebuild_from_grid()

    def _rebuild_from_grid(self):
        g = self._grid
        if not g:
            return
        for idx, (c, r) in enumerate(self._cells):
            if idx >= len(self.slots):
                break
            self.slots[idx] = {"x": g["x0"] + c * (g["w"] + g["gx"]),
                               "y": g["y0"] + r * (g["h"] + g["gy"]),
                               "w": g["w"], "h": g["h"]}

    def _drag_even(self, idx, cx, cy):
        """균등 모드 드래그: 이동=전체 함께, 크기조절=전체 같은 크기."""
        g = self._grid
        c, r = self._cells[idx]
        if self._mode == "resize":
            # 이 칸의 좌상단 기준으로 새 폭(비율 고정) → 전체 칸에 적용
            left = g["x0"] + c * (g["w"] + g["gx"])
            top = g["y0"] + r * (g["h"] + g["gy"])
            ratio = self._ratio if getattr(self, "_ratio", 0) else (g["w"] / g["h"] if g["h"] else 1)
            nw = max(40, cx - left)
            nh = nw / ratio
            # 격자가 캔버스를 벗어나지 않게 크기 상한
            max_w = (self.canvas_w - g["x0"] - (g["cols"] - 1) * g["gx"]) / g["cols"]
            max_h = (self.canvas_h - g["y0"] - (g["rows"] - 1) * g["gy"]) / g["rows"]
            if nw > max_w:
                nw = max_w; nh = nw / ratio
            if nh > max_h:
                nh = max_h; nw = nh * ratio
            g["w"], g["h"] = int(round(nw)), int(round(nh))
            _ = top
        else:
            # 이동: 이 칸이 커서를 따라가도록 격자 좌상단을 옮긴다(전체 함께)
            nx = cx - self._drag_off.x() - c * (g["w"] + g["gx"])
            ny = cy - self._drag_off.y() - r * (g["h"] + g["gy"])
            g["x0"] = int(round(max(0, min(nx, self.canvas_w - self._grid_w()))))
            g["y0"] = int(round(max(0, min(ny, self.canvas_h - self._grid_h()))))
        self._rebuild_from_grid()

    @staticmethod
    def _ranks(vals, tol):
        clusters = []
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        rank = [0] * len(vals)
        for i in order:
            placed = False
            for ci, cv in enumerate(clusters):
                if abs(vals[i] - cv) <= tol:
                    rank[i] = ci; placed = True; break
            if not placed:
                clusters.append(vals[i]); rank[i] = len(clusters) - 1
        return rank, len(clusters)

    def distribute_evenly(self):
        """모든 슬롯 크기를 (중앙값으로) 통일하고, 현재 범위 안에서 같은 간격으로 재배치."""
        n = len(self.slots)
        if n < 2:
            return
        ws = sorted(s["w"] for s in self.slots)
        hs = sorted(s["h"] for s in self.slots)
        mw, mh = ws[n // 2], hs[n // 2]
        cxs = [s["x"] + s["w"] / 2 for s in self.slots]
        cys = [s["y"] + s["h"] / 2 for s in self.slots]
        col_rank, ncols = self._ranks(cxs, mw * 0.5)
        row_rank, nrows = self._ranks(cys, mh * 0.5)
        minx = max(0, min(s["x"] for s in self.slots))
        maxx = min(self.canvas_w, max(s["x"] + s["w"] for s in self.slots))
        miny = max(0, min(s["y"] for s in self.slots))
        maxy = min(self.canvas_h, max(s["y"] + s["h"] for s in self.slots))

        def pos(rank, count, lo, hi, size):
            if count <= 1:
                return int(round((lo + hi) / 2 - size / 2))
            step = (hi - lo - size) / (count - 1)
            return int(round(lo + rank * step))

        for i, sl in enumerate(self.slots):
            sl["w"], sl["h"] = mw, mh
            sl["x"] = max(0, min(pos(col_rank[i], ncols, minx, maxx, mw), self.canvas_w - mw))
            sl["y"] = max(0, min(pos(row_rank[i], nrows, miny, maxy, mh), self.canvas_h - mh))
        self.update()
        self.changed.emit()

    def _snap(self, idx, x, y, w, h):
        candX = [(0, 0), (self.canvas_w - w, self.canvas_w)]
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
