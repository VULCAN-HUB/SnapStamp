import time
from PyQt5.QtCore import Qt, pyqtSignal, QVariantAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QPixmap, QKeySequence, QPainter, QColor
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy,
                             QPushButton, QApplication)
from ui.theme import INK, SURFACE, LINE, ACCENT, TEXT, MUTED, shadow


class ResultWindow(QWidget):
    home_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{INK};")
        self.setFocusPolicy(Qt.StrongFocus)  # 트리거 키 더블탭 감지용 포커스
        self._orig = None
        self._scaled = None          # 최종 표시 크기의 완성 사진(리빌 애니메이션 원본)
        self._qr_pms = (None, None)  # (wifi, photo) QR 원본
        self.reveal_enabled = True
        self.reveal_ms = 2000        # 등장 연출 길이(운영자 설정)
        self._anim = None
        self._motion_timer = None    # '움짤 제작 중' 점 애니메이션
        self._motion_ready = False
        self._motion_step = 3
        self._last_space = 0.0
        self.trigger_key = "Space"  # 재시작용 트리거 키(설정에서 지정한 키를 따름)
        h = QHBoxLayout(self); h.setContentsMargins(56, 36, 56, 36); h.setSpacing(48)

        # ── 왼쪽: 완성 이미지(사진에 꼭 맞는 흰 프레임 + 그림자) ──
        left = QVBoxLayout(); left.setSpacing(16)
        title = QLabel("완성!")
        title.setStyleSheet(f"color:{TEXT}; font-size:40px; font-weight:bold;")
        left.addWidget(title, 0, Qt.AlignHCenter)
        left.addStretch(1)
        # ⚠️ 흰 테두리를 두르면 실제 받는 파일과 달라 보인다(손님이 혼동).
        #    화면에 보이는 것 = 다운로드되는 파일 그대로가 되도록 여백 없이 이미지만 띄운다.
        self.frame = QWidget()
        self.frame.setStyleSheet("background:transparent;")
        shadow(self.frame, blur=48, dy=14, alpha=150)   # 깊이감만(흰 여백 없음)
        fl = QVBoxLayout(self.frame); fl.setContentsMargins(0, 0, 0, 0)
        self.image = QLabel("사진 합성 중…")
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setStyleSheet(f"background:transparent; color:#999; font-size:22px;")
        fl.addWidget(self.image)
        left.addWidget(self.frame, 0, Qt.AlignCenter)  # 사진 크기에 맞춰 중앙 배치
        left.addStretch(1)
        h.addLayout(left, 1)

        # ── 오른쪽: QR 카드(WiFi 연결 QR + 사진 QR) ──
        right = QVBoxLayout(); right.setSpacing(14); right.addStretch(1)

        # ① WiFi 연결 QR (설정 시에만 표시)
        self.wifi_title = QLabel("① WiFi 연결")
        self.wifi_title.setAlignment(Qt.AlignCenter)
        self.wifi_title.setStyleSheet(f"color:{TEXT}; font-size:24px; font-weight:bold;")
        right.addWidget(self.wifi_title)
        self.wifi_card = QWidget()
        self.wifi_card.setStyleSheet("background:white; border-radius:18px;")
        shadow(self.wifi_card, blur=36, dy=10, alpha=120)
        wl = QVBoxLayout(self.wifi_card); wl.setContentsMargins(16, 16, 16, 16)
        self.wifi_qr = QLabel("QR"); self.wifi_qr.setAlignment(Qt.AlignCenter)
        self.wifi_qr.setStyleSheet("background:transparent; color:#aaa;")
        wl.addWidget(self.wifi_qr)
        right.addWidget(self.wifi_card, 0, Qt.AlignCenter)

        self.qr_title = QLabel("사진 받기")
        self.qr_title.setAlignment(Qt.AlignCenter)
        self.qr_title.setStyleSheet(f"color:{TEXT}; font-size:24px; font-weight:bold;")
        right.addWidget(self.qr_title)
        self.qr_card = QWidget(); self.qr_card.setFixedSize(160, 160)   # 실제 크기는 화면 높이에 맞춰 다시 정한다
        self.qr_card.setStyleSheet("background:white; border-radius:20px;")
        shadow(self.qr_card, blur=40, dy=12, alpha=130)
        ql = QVBoxLayout(self.qr_card); ql.setContentsMargins(18, 18, 18, 18)
        self.qr = QLabel("QR"); self.qr.setAlignment(Qt.AlignCenter)
        self.qr.setStyleSheet("background:transparent; color:#aaa;")
        ql.addWidget(self.qr)
        right.addWidget(self.qr_card, 0, Qt.AlignCenter)
        # ③ 움직이는 4컷(GIF/MP4) QR — 생성이 끝나면 나타남
        self.motion_title = QLabel("③ 움짤 받기")
        self.motion_title.setAlignment(Qt.AlignCenter)
        self.motion_title.setStyleSheet(f"color:{TEXT}; font-size:24px; font-weight:bold;")
        right.addWidget(self.motion_title)
        self.motion_card = QWidget()
        self.motion_card.setStyleSheet("background:white; border-radius:18px;")
        shadow(self.motion_card, blur=36, dy=10, alpha=120)
        ml = QVBoxLayout(self.motion_card); ml.setContentsMargins(16, 16, 16, 16)
        self.motion_qr = QLabel("QR"); self.motion_qr.setAlignment(Qt.AlignCenter)
        self.motion_qr.setStyleSheet("background:transparent; color:#aaa;")
        ml.addWidget(self.motion_qr)
        right.addWidget(self.motion_card, 0, Qt.AlignCenter)
        self.motion_title.hide(); self.motion_card.hide()

        self.caption = QLabel("휴대폰으로 QR을 스캔하세요")
        self.caption.setAlignment(Qt.AlignCenter); self.caption.setWordWrap(True)
        self.caption.setStyleSheet(f"color:{MUTED}; font-size:19px;")
        right.addWidget(self.caption)
        # 링크 유효 범위 안내(로컬 전달일 때만) — 손님이 나중에 받으려다 낭패 보지 않게
        self.motion_status = QLabel("")
        self.motion_status.setAlignment(Qt.AlignCenter); self.motion_status.setWordWrap(True)
        self.motion_status.setStyleSheet(f"color:{MUTED}; font-size:15px;")
        right.addWidget(self.motion_status)
        self.validity = QLabel("이 QR은 부스 운영 중에만 사용할 수 있어요 · 지금 받아가세요")
        self.validity.setAlignment(Qt.AlignCenter); self.validity.setWordWrap(True)
        self.validity.setStyleSheet("color:#FFD98A; font-size:15px; font-weight:600;")
        right.addWidget(self.validity)
        right.addSpacing(20)
        again = QPushButton("▶ 다시 촬영"); again.setObjectName("primary")
        again.setMinimumHeight(56); again.setMinimumWidth(220)
        again.clicked.connect(self.home_requested.emit)
        right.addWidget(again, 0, Qt.AlignCenter)
        self.tip = QLabel("스페이스바를 빠르게 두 번 눌러도 됩니다")
        tip = self.tip
        tip.setAlignment(Qt.AlignCenter)
        tip.setStyleSheet(f"color:{MUTED}; font-size:16px;")
        right.addWidget(tip)
        right.addStretch(1)
        h.addLayout(right)
        self._server = None

    def show_result(self, image_path, qr_path, mode, wifi_qr_path=None, motion_expected=False):
        self._orig = QPixmap(image_path)
        self._rescale()
        wifi_pm = QPixmap(wifi_qr_path) if wifi_qr_path else QPixmap()
        show_wifi = not wifi_pm.isNull()
        # ⚠️ 움짤이 나중에 추가되며 QR 2개→3개로 튀면 손님이 놀란다.
        #    처음부터 자리를 잡아두고 '제작 중'을 보여준 뒤, 준비되면 QR만 바꿔 끼운다.
        n_cards = (1 if show_wifi else 0) + 1
        side = 210 if n_cards == 2 else 270
        # ⚠️ QR 카드를 고정 크기로 두면 세로가 짧은 모니터(720p 등)에서 화면을 넘긴다.
        #    쓸 수 있는 높이에 맞춰 줄인다 — 스캔에는 140px 면 충분하다.
        avail = self.height() if self.height() > 200 else 720
        side = max(140, min(side, (avail - 260) // n_cards - 40))
        card = side + 40
        self.wifi_title.setVisible(show_wifi)
        self.wifi_card.setVisible(show_wifi)
        step = 1
        if show_wifi:
            self.wifi_card.setFixedSize(card, card)
            self.wifi_qr.setPixmap(wifi_pm.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.wifi_title.setText("① WiFi 연결")
            step = 2
        self.qr_title.setText(("② 사진·움짤 받기" if motion_expected else "② 사진 받기")
                              if show_wifi else
                              ("사진·움짤 받기" if motion_expected else "사진 받기"))
        self.qr_card.setFixedSize(card, card)
        qr_side = side
        qpm = QPixmap(qr_path)
        self._qr_pms = (wifi_pm if show_wifi else None, qpm if not qpm.isNull() else None,
                        side if show_wifi else 0, qr_side)
        if not qpm.isNull():
            self.qr.setPixmap(qpm.scaled(qr_side, qr_side, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        # QR 하나로 통합 — 접속 페이지에서 사진과 움짤을 함께 받는다
        self.hide_motion_qr()
        if motion_expected:
            self._start_motion_wait()
        else:
            self.motion_status.setText("")
        if show_wifi:
            self.caption.setText("① WiFi 연결 → ② QR 스캔해서 받기")
        else:
            self.caption.setText("휴대폰으로 QR을 스캔하면\n사진을 받을 수 있어요"
                                 if mode == "cloud" else "같은 WiFi에 연결한 뒤\nQR을 스캔하세요")
        self.validity.setVisible(mode != "cloud")   # 클라우드면 앱 종료 후에도 유효
        self.setFocus()  # 더블탭 스페이스 입력을 받도록 포커스
        self._start_reveal()

    def _start_motion_wait(self):
        """움짤이 아직 만들어지는 중임을 QR 아래 문구로 알림(QR은 하나로 유지)."""
        self._motion_ready = False
        self._motion_dots = 0
        if self._motion_timer is None:
            self._motion_timer = QTimer(self)
            self._motion_timer.setInterval(450)
            self._motion_timer.timeout.connect(self._tick_motion_wait)
        self._tick_motion_wait()
        self._motion_timer.start()

    def _tick_motion_wait(self):
        self._motion_dots = (self._motion_dots + 1) % 4
        self.motion_status.setText("움짤 만드는 중" + "." * self._motion_dots
                                   + "  (같은 QR에서 함께 받을 수 있어요)")

    def show_motion_qr(self, _qr_path: str = "", ext: str = "gif"):
        """움짤 준비 완료 — QR은 그대로 두고 안내 문구만 바꾼다."""
        if self._motion_timer is not None:
            self._motion_timer.stop()
        self._motion_ready = True
        self.motion_status.setText(f"사진 · 움짤({ext.upper()}) 모두 준비 완료")

    def motion_failed(self, _msg=""):
        """생성 실패 시 손님이 계속 기다리지 않도록 안내 정리."""
        if self._motion_timer is not None:
            self._motion_timer.stop()
        self.motion_status.setText("")

    def hide_motion_qr(self):
        if self._motion_timer is not None:
            self._motion_timer.stop()
        self.motion_title.hide(); self.motion_card.hide()

    # ── 완성 리빌 연출 ───────────────────────────────────────────────
    def set_reveal_enabled(self, on: bool, seconds: float = None):
        self.reveal_enabled = bool(on)
        if seconds:
            self.reveal_ms = max(500, int(float(seconds) * 1000))

    def _stop_reveal(self):
        if self._anim is not None:
            self._anim.stop()
            self._anim = None

    def _start_reveal(self):
        """필름이 현상되듯 사진이 어둠에서 떠오르고, 이어서 QR이 커지며 등장."""
        self._stop_reveal()
        if not self.reveal_enabled or self._scaled is None:
            self._apply_reveal(1.0)
            return
        self._apply_reveal(0.0)
        a = QVariantAnimation(self)
        a.setStartValue(0.0); a.setEndValue(1.0)
        a.setDuration(self.reveal_ms)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.valueChanged.connect(lambda v: self._apply_reveal(float(v)))
        a.finished.connect(lambda: self._apply_reveal(1.0))
        self._anim = a
        a.start()

    def _apply_reveal(self, t: float):
        """t=0 어둡고 살짝 작음 → t=1 완전한 사진. QR은 중반부터 커지며 등장."""
        pm = self._scaled
        if pm is not None and not pm.isNull():
            if t >= 1.0:
                self.image.setPixmap(pm)
            else:
                out = QPixmap(pm.size()); out.fill(Qt.transparent)
                p = QPainter(out)
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                s = 0.955 + 0.045 * t                      # 살짝 커지며 등장
                w, hgt = max(1, int(pm.width() * s)), max(1, int(pm.height() * s))
                p.drawPixmap((pm.width() - w) // 2, (pm.height() - hgt) // 2,
                             pm.scaled(w, hgt, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                # 어둠이 걷히며 상이 떠오름(현상 느낌)
                p.fillRect(out.rect(), QColor(0, 0, 0, int(235 * (1.0 - t))))
                p.end()
                self.image.setPixmap(out)
        # QR은 사진이 어느 정도 드러난 뒤(0.45~1.0) 커지며 등장
        wifi_pm, qr_pm, wifi_side, qr_side = self._qr_pms if len(self._qr_pms) == 4 else (None, None, 0, 0)
        k = 0.0 if t < 0.45 else min(1.0, (t - 0.45) / 0.55)
        scale = 0.82 + 0.18 * k
        if qr_pm is not None and qr_side:
            side = max(1, int(qr_side * scale))
            self.qr.setPixmap(qr_pm.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if wifi_pm is not None and wifi_side:
            side = max(1, int(wifi_side * scale))
            self.wifi_qr.setPixmap(wifi_pm.scaled(side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _rescale(self):
        if self._orig is None or self._orig.isNull():
            return
        # ⚠️ self.width()/height()를 기준으로 하면 setFixedSize→레이아웃확대→resize→…
        # 무한 확대 루프가 생긴다. 고정값인 '모니터 화면 크기'를 기준으로 한 번만 계산.
        scr = QApplication.primaryScreen().availableGeometry()
        avail_w = max(240, int(scr.width() * 0.52))   # 좌측 사진 영역(우측 QR 열 제외)
        avail_h = max(240, scr.height() - 150)
        sc = self._orig.scaled(avail_w, avail_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._scaled = sc            # 리빌 애니메이션이 이 픽스맵을 원본으로 사용
        self.image.setPixmap(sc)
        self.image.setFixedSize(sc.size())

    def set_trigger(self, key):
        self.trigger_key = key or "Space"
        self.tip.setText(f"‘{self.trigger_key}’ 키를 빠르게 두 번 눌러도 됩니다")

    def trigger_pressed(self):
        """트리거 키 1회 입력(앱 전역 라우터가 호출). 빠르게 두 번이면 다음 손님으로.

        ⚠️ keyPressEvent 로 받으면 안 된다 — 보조 모니터(손님) 창이 활성 창을 가져가면
        이 위젯에는 키가 오지 않는다. 라우터가 포커스와 무관하게 넘겨준다.
        """
        now = time.monotonic()
        if self._last_space and (now - self._last_space) < 0.45:
            self._last_space = 0.0
            self._stop_reveal()          # 연출 중이면 중단하고 즉시 다음 손님으로
            self.home_requested.emit()  # 트리거 키 짧게 연속 두 번 → 처음 촬영으로
        else:
            self._last_space = now

    def attach_server(self, server):
        self._server = server

    def release_server(self):
        if self._server:
            self._server.stop(); self._server = None
