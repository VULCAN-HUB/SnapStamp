import os
import time
from PyQt5.QtCore import pyqtSignal, Qt, QEvent, QSize, QTimer
from PyQt5.QtGui import QPixmap, QKeySequence
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                             QSpinBox, QPushButton, QComboBox, QLineEdit, QFileDialog,
                             QSizePolicy, QApplication, QDialog, QCheckBox, QScrollArea,
                             QFrame)
from ui.theme import (make_header, INK, SURFACE, SURFACE2, LINE, ACCENT, TEXT, MUTED,
                      OK_GREEN, GOLD, HAIR, HAIR_HI, shadow, letter_spacing,
                      NoWheelSpinBox, NoWheelComboBox, NoWheelSlider)
from ui.slot_editor import SlotEditor
from ui import icons


class KeyCaptureButton(QPushButton):
    """클릭하면 다음에 누른 키를 트리거 키로 즉시 등록하는 버튼(텍스트 입력 아님)."""
    key_changed = pyqtSignal(str)

    def __init__(self, key_name="Space", parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self._capturing = False
        self.set_key(key_name)
        self.clicked.connect(self._begin)

    def set_key(self, name):
        self.key_name = name or "Space"
        self.setText(f"  {self.key_name}")
        self.setIcon(icons.icon("keyboard", MUTED, 17)); self.setIconSize(QSize(17, 17))
        self.setStyleSheet("")

    def _begin(self):
        self._capturing = True
        self.setText("아무 키나 누르세요…")
        self.setStyleSheet(f"border-color:{ACCENT}; color:{ACCENT};")
        self.grabKeyboard()

    def keyPressEvent(self, e):
        if self._capturing:
            k = e.key()
            if k in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta):
                return
            name = QKeySequence(k).toString()
            if not name:
                return
            self._capturing = False
            self.releaseKeyboard()
            self.set_key(name)
            self.key_changed.emit(self.key_name)
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e):
        if self._capturing:
            self._capturing = False
            self.releaseKeyboard()
            self.set_key(self.key_name)
        super().focusOutEvent(e)


def _title(t):
    lab = QLabel(t); lab.setStyleSheet(f"color:{TEXT}; font-size:23px; font-weight:bold;")
    return lab


def _flabel(t):
    lab = QLabel(t); lab.setStyleSheet(f"color:{MUTED}; font-size:17px; font-weight:600;")
    return lab


def _eyebrow(t):
    """섹션 마커 — 골드 대문자 소형 라벨(프리미엄 시그널). 자간은 QFont로(QSS 무시됨)."""
    lab = QLabel(t.upper())
    lab.setStyleSheet(f"color:{GOLD}; font-size:14px; font-weight:700;")
    letter_spacing(lab, 2.2)
    return lab


def _card():
    w = QWidget()
    # 깊이는 헤어라인 보더 + 명도 사다리로. 그림자는 아주 은은하게만 보조.
    w.setStyleSheet(f"background:{SURFACE}; border:1px solid {LINE}; border-radius:16px;")
    shadow(w, blur=20, dy=5, alpha=55)
    return w


class SetupWindow(QWidget):
    start_requested = pyqtSignal()
    test_camera_requested = pyqtSignal()
    camera_search_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setFocusPolicy(Qt.StrongFocus)
        self.trigger_key = config.get("trigger_key", "Space")
        self._ready_at = 0.0  # 화면 진입 직후 트리거 무시(오탭 방지) 시각
        self._suppress_reconnect = True  # 초기 위젯 세팅 중 자동 재연결 억제
        self._last_frame = None          # 최근 라이브 프레임(결과 미리보기용)
        QApplication.instance().installEventFilter(self)

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        hdr = make_header(self)
        hdr.quit_btn.clicked.connect(self.quit_requested.emit)
        root.addWidget(hdr)

        # 상세 설정 위젯들은 별도 '환경설정' 창(self.prefs)에 담는다 → 운영자 화면은 핵심만.
        self._build_settings_widgets()
        self.prefs = self._build_prefs_dialog()

        # ⚠️ 본문을 스크롤 영역에 담는다 — **창은 자기 최소 폭보다 작아질 수 없어서**, 내용이
        #    화면보다 넓으면 전체화면이 옆 모니터까지 넘친다(실측: 최소 폭 2201px, 주 모니터 1536px).
        #    스크롤에 담으면 어떤 해상도에서도 창이 화면 안에 들어오고, 모자라면 스크롤로 흡수한다.
        body_host = QWidget(); body_host.setStyleSheet("background:transparent;")
        body = QHBoxLayout(body_host); body.setContentsMargins(28, 22, 28, 14); body.setSpacing(22)
        body_scroll = QScrollArea(); body_scroll.setWidgetResizable(True)
        body_scroll.setFrameShape(QFrame.NoFrame)
        body_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        body_scroll.setWidget(body_host)
        root.addWidget(body_scroll, 1)

        # ══ 왼쪽: 라이브 미리보기(카메라 16:9에 딱 맞춤) + 구성 요약 ══
        LEFT_W = 460
        leftw = QWidget(); leftw.setFixedWidth(LEFT_W)
        left = QVBoxLayout(leftw); left.setContentsMargins(0, 0, 0, 0); left.setSpacing(16)
        prev = _card()
        pv = QVBoxLayout(prev); pv.setContentsMargins(18, 16, 18, 18); pv.setSpacing(12)
        ph = QHBoxLayout()
        ph.addWidget(_eyebrow("라이브 미리보기")); ph.addStretch(1)
        self.cam_status = QLabel("● 대기")
        self.cam_status.setStyleSheet(f"color:{MUTED}; font-size:15px; font-weight:700;")
        ph.addWidget(self.cam_status)
        # 미리보기 버튼 대신 작은 '다시 연결' 아이콘(오조작·군더더기 최소화)
        self.reconnect_btn = QPushButton()
        self.reconnect_btn.setIcon(icons.icon("refresh-cw", MUTED, 15)); self.reconnect_btn.setFixedSize(30, 30)
        self.reconnect_btn.setToolTip("카메라 다시 연결")
        self.reconnect_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {HAIR};border-radius:9px;}}"
            f"QPushButton:hover{{border-color:{HAIR_HI};}}")
        self.reconnect_btn.clicked.connect(self.test_camera_requested.emit)
        ph.addSpacing(6); ph.addWidget(self.reconnect_btn)
        pv.addLayout(ph)
        self.preview = QLabel("카메라를 자동 연결하고 있어요…")
        self.preview.setAlignment(Qt.AlignCenter); self.preview.setWordWrap(True)
        self.preview.setStyleSheet(
            f"background:#05070b; border:1px solid {LINE}; border-radius:12px;"
            f"color:{MUTED}; font-size:16px;")
        self.preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # 카메라 16:9에 딱 맞는 높이로 고정 → 세로로 남는 빈 공간 낭비 제거
        self.preview.setFixedHeight(int((LEFT_W - 36) * 9 / 16))
        pv.addWidget(self.preview)
        left.addWidget(prev)

        # 구성 요약 카드(빈 공간을 유용하게 — 현재 설정을 한눈에)
        info = _card()
        iv = QVBoxLayout(info); iv.setContentsMargins(18, 14, 18, 14); iv.setSpacing(7)
        iv.addWidget(_eyebrow("현재 설정 (요약)"))
        self._info_rows = {}
        for key, label in (("layout", "레이아웃"), ("res", "촬영 해상도"),
                           ("quality", "저장 화질"), ("tone", "사진 색감"),
                           ("brand", "문구·로고"), ("countdown", "카운트다운"),
                           ("cuts", "컷 수"), ("flash", "플래시"), ("sound", "효과음"),
                           ("mirror", "거울 모드"), ("delivery", "전달 방식"),
                           ("wifi", "손님 WiFi 안내"), ("guestaddr", "손님 접속 주소"),
                           ("readyto", "준비화면 복귀"),
                           ("abandonto", "촬영중 방치 취소"),
                           ("autoreturn", "완성 후 복귀"),
                           ("save", "저장 위치"), ("trigger", "트리거 키")):
            row = QHBoxLayout()
            k = QLabel(label); k.setStyleSheet(f"color:{MUTED}; font-size:15px;")
            val = QLabel("—"); val.setStyleSheet(f"color:{TEXT}; font-size:15px; font-weight:600;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(k); row.addStretch(1); row.addWidget(val)
            iv.addLayout(row); self._info_rows[key] = val
        left.addWidget(info)
        left.addStretch(1)
        # ⚠️ 좌측 내용(프리뷰+요약)이 화면 논리 높이를 넘으면 하단바가 잘린다.
        #    스크롤 영역에 담아 어떤 해상도·배율에서도 하단바가 항상 보이게 한다.
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFixedWidth(LEFT_W + 14)
        left_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        left_scroll.setWidget(leftw)
        body.addWidget(left_scroll)

        # ══ 오른쪽: 큰 슬롯 배치 에디터 ══
        slot_card = _card()
        sv = QVBoxLayout(slot_card); sv.setContentsMargins(22, 18, 22, 20); sv.setSpacing(10)
        sh = QHBoxLayout()
        tbox = QVBoxLayout(); tbox.setSpacing(3)
        tbox.addWidget(_eyebrow("레이아웃 · 사진 배치"))
        t2 = QLabel("사진 배치 (4컷)")
        t2.setStyleSheet(f"color:{TEXT}; font-size:25px; font-weight:800;")
        tbox.addWidget(t2)
        sh.addLayout(tbox); sh.addStretch(1)
        # 레이아웃 라이브러리 = 예시(기본 제공) + 사용자가 추가한 자체 템플릿
        self.user_layouts = [dict(u) for u in config.get("user_layouts", [])]

        # 에디터 먼저 생성(버튼 콜백이 참조) — 초기 상태는 config 그대로 로드
        cs = config.get("canvas_size", [800, 600])
        self.editor = SlotEditor(config.get("slots", []), canvas_size=tuple(cs))
        self.editor.changed.connect(self._on_slots_edited)
        if config.get("template_path"):
            self._apply_template(config["template_path"])
        if config.get("even_layout"):
            self.editor.set_even(True, normalize=False)

        sh.addWidget(_flabel("레이아웃"))
        prev_b = QPushButton("◀"); prev_b.setFixedWidth(30); prev_b.setToolTip("이전 레이아웃")
        prev_b.clicked.connect(lambda: self._step_layout(-1)); sh.addWidget(prev_b)
        self.layout_box = NoWheelComboBox()
        self.layout_box.setMinimumWidth(150)
        sh.addWidget(self.layout_box)
        next_b = QPushButton("▶"); next_b.setFixedWidth(30); next_b.setToolTip("다음 레이아웃")
        next_b.clicked.connect(lambda: self._step_layout(1)); sh.addWidget(next_b)

        # ⚠️ 여기서 줄을 바꾼다. 버튼을 한 줄에 다 넣으면 이 화면의 **최소 폭이 2201px** 이 되어
        #    1536px 짜리 주 모니터에서 전체화면이 **옆 모니터까지 넘친다**(실측). 창은 최소 폭보다
        #    작아질 수 없다 — 줄을 나눠 최소 폭을 낮추는 것이 근본 해결이다.
        sv.addLayout(sh)
        sh = QHBoxLayout(); sh.setSpacing(8)
        sh.addStretch(1)

        add_b = QPushButton("  이미지 추가")
        add_b.setIcon(icons.icon("image", MUTED, 17)); add_b.setIconSize(QSize(17, 17))
        add_b.setToolTip("자체 제작한 템플릿 이미지를 새 레이아웃으로 추가합니다")
        add_b.clicked.connect(lambda: self._add_template_layout()); sh.addWidget(add_b)
        self.rename_btn = QPushButton("이름")
        self.rename_btn.setToolTip("레이아웃 이름 변경")
        self.rename_btn.clicked.connect(self._rename_layout); sh.addWidget(self.rename_btn)
        self.del_btn = QPushButton("삭제")
        self.del_btn.clicked.connect(self._delete_layout); sh.addWidget(self.del_btn)

        self.even_btn = QPushButton("  균등 OFF")
        self.even_btn.setCheckable(True)
        self.even_btn.setChecked(bool(config.get("even_layout")))
        self.even_btn.setIconSize(QSize(17, 17))
        self.even_btn.setToolTip("켜면 모든 칸이 하나의 격자처럼 묶여, 한 칸을 옮기면 전체가 함께 이동하고 "
                                 "크기를 바꾸면 전체가 같은 크기로 조절됩니다")
        self.even_btn.toggled.connect(self._toggle_even)
        sh.addWidget(self.even_btn)
        self._style_even_btn()

        self.detect_btn = QPushButton()
        self.detect_btn.setIcon(icons.icon("search", MUTED, 17))
        self.detect_btn.setIconSize(QSize(17, 17))
        self.detect_btn.setToolTip("템플릿 이미지의 사진 자리(투명 구멍·초록 칠)를 읽어 칸을 맞춥니다")
        self.detect_btn.clicked.connect(self._detect_slots_now)
        sh.addWidget(self.detect_btn)

        ex_btn = QPushButton()
        ex_btn.setToolTip("예시 템플릿 PNG 내보내기")
        ex_btn.setIcon(icons.icon("download", MUTED, 17)); ex_btn.setIconSize(QSize(17, 17))
        ex_btn.clicked.connect(self._export_examples)
        sh.addWidget(ex_btn)
        sv.addLayout(sh)
        hint = QLabel("드래그로 이동 · 우하단 모서리로 크기조절 · 칸 클릭 후 방향키로 미세이동(Shift=10px) · "
                      "◀▶ 방향키로 내 레이아웃 전환(예시 제외)")
        hint.setStyleSheet(f"color:{MUTED}; font-size:15px;")
        # ⚠️ 줄바꿈을 켜지 않으면 이 라벨의 '글자 폭'이 곧 화면의 최소 폭이 된다 —
        #    창이 그보다 작아질 수 없어 전체화면이 **옆 모니터까지 넘친다**(실측 2201px).
        hint.setWordWrap(True)
        hint.setMinimumWidth(1)
        sv.addWidget(hint)

        # 콤보 채우기 + 현재 config 상태에 맞는 항목 선택(시그널 차단으로 에디터 유지)
        self._reload_layout_combo()
        init_name = config.get("active_layout") or self._match_entry(
            cs, config.get("slots", []), config.get("template_path", ""))
        if not init_name and (config.get("template_path") or "").strip():
            # 기존 설정의 자체 템플릿이 라이브러리에 없으면 사용자 레이아웃으로 등록
            # (그래야 다른 레이아웃으로 갔다가 되돌아올 수 있고, 잃어버리지 않는다)
            tp = config["template_path"].strip()
            init_name = self._unique_layout_name(os.path.splitext(os.path.basename(tp))[0])
            self.user_layouts.append({"name": init_name, "builtin": False, "template_path": tp,
                                      "canvas_size": [self.editor.canvas_w, self.editor.canvas_h],
                                      "slots": self.editor.get_slots(), "even": self.editor.even})
            self._reload_layout_combo(select=init_name)
        self.layout_box.blockSignals(True)
        idx = self.layout_box.findData(init_name) if init_name else -1
        if idx >= 0:
            self.layout_box.setCurrentIndex(idx)
        self.layout_box.blockSignals(False)
        # ⚠️ 위에서 시그널을 막고 인덱스를 넣었으므로 _select_layout 이 안 불린다.
        #    활성 레이아웃 이름을 여기서 직접 세워야 편집이 엉뚱한 레이아웃에 저장되지 않는다.
        # ⚠️ 매칭되는 항목이 없으면 **활성 이름을 비워 둔다.** 콤보 첫 항목(예시) 이름을 활성으로
        #    저장해 버리면, 다음 실행에서 "이름과 배치 일치" 로직이 그 예시 배치로 **사용자 슬롯을
        #    덮어쓴다**(구버전 설정으로 켠 뒤 재시작하면 배치가 통째로 바뀌는 실제 결함).
        self._active_layout = init_name or ""
        # ⚠️ 그리고 **이름과 배치가 어긋난 채로 시작하면 안 된다.** active_layout 은 아이돌형인데
        #    저장된 slots/canvas 는 세로형인 설정으로 켜면, 화면엔 아이돌형이라 뜨고 사진은 옛 칸에
        #    들어가 "비율이 깨진" 것처럼 보인다(실측). 이름이 가리키는 항목을 진짜로 적용한다.
        # ⚠️ **설정이 이름을 명시했을 때만** 적용한다. 이름이 없어 콤보 첫 항목으로 떨어진 경우까지
        #    적용하면, 저장돼 있던 사용자 슬롯을 엉뚱한 레이아웃 값으로 덮어써 버린다.
        e0 = self._find_entry(init_name) if init_name else None
        if e0 and (list(e0["canvas_size"]) != [self.editor.canvas_w, self.editor.canvas_h]
                   or [dict(s) for s in e0["slots"]] != self.editor.get_slots()):
            self._select_layout(init_name)
        self._update_layout_buttons()
        self.layout_box.currentIndexChanged.connect(
            lambda _i: self._select_layout(self.layout_box.currentData()))

        # 사진 칸 배치는 **관리자 화면에서 바로** 만진다(오너 지시 2026-08-12 — 설정 창에서 원복).
        sv.addWidget(self.editor, 1)
        body.addWidget(slot_card, 1)

        # ══ 하단 버튼바 ══
        bottom = QWidget(); bottom.setStyleSheet(f"background:{INK}; border-top:1px solid {LINE};")
        bl = QHBoxLayout(bottom); bl.setContentsMargins(28, 16, 28, 16); bl.setSpacing(14)
        self.settings_btn = QPushButton("  설정")
        self.settings_btn.setIcon(icons.icon("sliders-horizontal", TEXT, 18))
        self.settings_btn.setIconSize(QSize(18, 18)); self.settings_btn.setMinimumHeight(48)
        self.settings_btn.clicked.connect(self.open_settings)
        bl.addWidget(self.settings_btn)
        bl.addStretch(1)
        self.hint2 = QLabel("")
        self.hint2.setStyleSheet(f"color:{MUTED}; font-size:17px;")
        # ⚠️ 줄바꿈만 켜면 좁은 칸에 갇혀 세로로 뭉친다 — 남는 가로 공간을 받도록 stretch 를 준다.
        self.hint2.setWordWrap(True)
        self.hint2.setMinimumWidth(1)
        self.hint2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bl.addWidget(self.hint2, 1); bl.addSpacing(8)
        self.start_btn = QPushButton("  촬영 시작"); self.start_btn.setObjectName("primary")
        self.start_btn.setIcon(icons.icon("camera", "#FFFFFF", 20)); self.start_btn.setIconSize(QSize(20, 20))
        self.start_btn.setMinimumWidth(210); self.start_btn.setMinimumHeight(54)
        self.start_btn.clicked.connect(self.start_requested.emit)
        bl.addWidget(self.start_btn)
        root.addWidget(bottom)

        self._sync_hint()
        self._refresh_info()
        # 초기 세팅 끝 → 이제부터 카메라 선택 변경 시 자동 재연결
        self._suppress_reconnect = False
        self.backend_box.currentTextChanged.connect(self._on_camera_changed)
        self.device_combo.currentIndexChanged.connect(self._on_camera_changed)

    # ── 상세 설정 위젯 생성(환경설정 창에 담김) ──
    def _build_settings_widgets(self):
        cfg = self.config
        self.template_edit = QLineEdit(cfg.get("template_path", ""))
        self.template_edit.setPlaceholderText("템플릿 PNG (없으면 흰 배경)")
        self.save_edit = QLineEdit(cfg.get("save_path", "results"))
        self.countdown = NoWheelSpinBox(); self.countdown.setRange(1, 10)
        self.countdown.setValue(cfg.get("countdown_sec", 3))
        self.qr_delay = NoWheelSpinBox(); self.qr_delay.setRange(5, 120)
        self.qr_delay.setValue(cfg.get("qr_prompt_delay", 30))
        self.trigger_btn = KeyCaptureButton(cfg.get("trigger_key", "Space"))
        self.trigger_btn.key_changed.connect(lambda k: setattr(self, "trigger_key", k))
        self.backend_box = NoWheelComboBox(); self.backend_box.addItems(["webcam", "mock"])
        self.backend_box.setCurrentText(cfg.get("camera", {}).get("backend", "mock"))
        self.device_combo = NoWheelComboBox()
        cur_name = cfg.get("camera", {}).get("device_name", "")
        self.device_combo.addItem(cur_name if cur_name else "자동 감지 중…", cur_name)
        # 촬영 해상도
        self.res_box = NoWheelComboBox()
        # 처리 해상도. 기본 FHD(약한 PC 권장). 4K는 고사양 PC용 — 4K 소스를 그대로 처리한다.
        # (부스 출력엔 FHD면 충분하나, 좋은 기기로 넘어갈 때를 위해 상위 옵션을 남겨둠)
        self._res_map = {"1920 × 1080 (FHD · 권장)": (1920, 1080), "1280 × 720 (빠름)": (1280, 720),
                         "2560 × 1440 (QHD · 고사양)": (2560, 1440), "3840 × 2160 (4K · 고사양)": (3840, 2160)}
        self.res_box.addItems(list(self._res_map.keys()))
        cw = cfg.get("camera", {}).get("width", 1920)
        # 저장된 폭에 가장 가까운 항목 선택
        keys = list(self._res_map.values())
        best = min(range(len(keys)), key=lambda i: abs(keys[i][0] - cw))
        self.res_box.setCurrentIndex(best)
        # 저장 화질(JPEG 품질)
        self.quality_box = NoWheelComboBox()
        self._q_map = {"최고 (선명·용량↑)": 97, "높음 (균형)": 92, "표준 (용량↓)": 88}
        self.quality_box.addItems(list(self._q_map.keys()))
        qv = cfg.get("jpeg_quality", 97)
        self.quality_box.setCurrentIndex(0 if qv >= 96 else (1 if qv >= 90 else 2))
        # 완성 후 자동으로 다음 손님(대기)으로 복귀
        self.autoreturn = NoWheelSpinBox(); self.autoreturn.setRange(0, 120)
        self.autoreturn.setValue(cfg.get("auto_return_sec", 0))
        self.autoreturn.setSuffix(" 초 (0=수동)")
        # 촬영 준비 화면에서 손님이 그냥 가버렸을 때 대기 화면으로 자동 복귀
        self.ready_timeout = NoWheelSpinBox(); self.ready_timeout.setRange(0, 300)
        self.ready_timeout.setValue(cfg.get("ready_timeout_sec", 30))
        self.ready_timeout.setSuffix(" 초 (0=끄기)")
        # 촬영 도중(컷 사이) 손님이 가버렸을 때 세션 폐기
        self.abandon_timeout = NoWheelSpinBox(); self.abandon_timeout.setRange(0, 300)
        self.abandon_timeout.setValue(cfg.get("abandon_timeout_sec", 60))
        self.abandon_timeout.setSuffix(" 초 (0=끄기)")
        # 토글
        self.flash_chk = QCheckBox("촬영 순간 흰 플래시")
        self.flash_chk.setChecked(cfg.get("flash_enabled", True))
        self.sound_chk = QCheckBox("효과음(비프·셔터·완료)")
        self.sound_chk.setChecked(cfg.get("sound_enabled", True))
        self.mirror_chk = QCheckBox("미리보기 좌우 반전(거울 모드)")
        self.mirror_chk.setChecked(cfg.get("mirror_preview", False))
        self.keepcuts_chk = QCheckBox("개별 컷 원본도 저장 폴더에 보관")
        self.keepcuts_chk.setChecked(cfg.get("keep_cuts", False))
        # 전달 방식 — 기본은 로컬(사진이 행사장 밖으로 안 나감). 클라우드는 명시 옵트인.
        self.share_port = NoWheelSpinBox(); self.share_port.setRange(1024, 65535)
        self.share_port.setValue(int(cfg.get("share_port", 8765)))
        self.share_port.setSuffix(" (공유 포트)")
        self.gif_chk = QCheckBox("움직이는 4컷(움짤) 만들기")
        self.gif_chk.setChecked(cfg.get("gif_enabled", True))
        self.gif_format = NoWheelComboBox(); self.gif_format.addItems(["GIF", "MP4"])
        self.gif_format.setCurrentText(cfg.get("gif_format", "GIF"))
        self.gif_width = NoWheelSpinBox(); self.gif_width.setRange(360, 1280)
        self.gif_width.setSingleStep(60); self.gif_width.setValue(int(cfg.get("gif_width", 720)))
        self.gif_width.setSuffix(" px (가로)")
        self.gif_fps = NoWheelSpinBox(); self.gif_fps.setRange(6, 20)
        self.gif_fps.setValue(int(cfg.get("gif_fps", 12))); self.gif_fps.setSuffix(" fps")
        self.reveal_chk = QCheckBox("완성 사진 등장 연출(리빌) 사용")
        self.reveal_chk.setChecked(cfg.get("reveal_enabled", True))
        self.reveal_sec = NoWheelSpinBox(); self.reveal_sec.setRange(1, 6)
        self.reveal_sec.setValue(int(cfg.get("reveal_sec", 2)))
        self.reveal_sec.setSuffix(" 초 (연출 길이)")
        self.cloud_chk = QCheckBox("클라우드 공유(외부 서버 업로드) 사용")
        self.cloud_chk.setChecked(cfg.get("cloud_share_enabled", False))
        # 손님 연결 안내 — 완성 화면에 WiFi 접속 QR을 함께 표시(손님이 원탭 접속)
        gw = cfg.get("guest_wifi", {}) or {}
        self.wifi_mode_box = NoWheelComboBox()
        self.wifi_mode_box.addItems(["표시 안 함", "현재 WiFi", "노트북 모바일 핫스팟"])
        self.wifi_mode_box.setCurrentIndex(
            {"off": 0, "current": 1, "hotspot": 2}.get(gw.get("mode", "off"), 0))
        self.wifi_ssid = QLineEdit(gw.get("ssid", ""))
        self.wifi_ssid.setPlaceholderText("WiFi 이름(SSID)")
        self.wifi_pw = QLineEdit(gw.get("password", ""))
        self.wifi_pw.setPlaceholderText("WiFi 비밀번호(없으면 비움)")
        # 초기 인덱스 설정 뒤에 연결 → 시작 시 불필요한 자동감지 실행 방지
        self.wifi_mode_box.currentIndexChanged.connect(self._on_wifi_mode_changed)
        # ⚠️ 장소가 바뀌면 WiFi 이름도 바뀐다. '현재 WiFi' 안내인데 지난 장소 이름이 그대로 남아
        #    있으면 손님에게 **틀린 망**을 안내하게 된다 → 시작할 때 지금 연결된 이름으로 갱신.
        #    비밀번호는 건드리지 않는다(저장된 자격증명을 자동으로 꺼내 보여주지 않는다).
        if self.wifi_mode_box.currentIndex() == 1:
            QTimer.singleShot(0, self._autofill_wifi)

        # ── 손님 받기 페이지(브랜딩) ──
        self.page_bg = QLineEdit(cfg.get("page_bg_color", "#0B0E13"))
        self.page_bg.setPlaceholderText("#0B0E13")
        self.page_fg = QLineEdit(cfg.get("page_text_color", "#EEF1F7"))
        self.page_fg.setPlaceholderText("#EEF1F7")
        self.page_logo = QLineEdit(cfg.get("page_logo_path", ""))
        self.page_logo.setPlaceholderText("로고 PNG (비우면 표시 안 함)")
        self.page_title = QLineEdit(cfg.get("page_title", "사진이 준비되었어요"))
        self.page_title.setPlaceholderText("행사 문구 (예: 2026 SEOUL POPUP)")
        # ── 브랜딩 · 색감 ──
        from core.tone import PRESET_NAMES
        self.tone_box = NoWheelComboBox(); self.tone_box.addItems(PRESET_NAMES)
        self.tone_box.setCurrentText(cfg.get("tone") or PRESET_NAMES[0])
        self.bg_color = QLineEdit(cfg.get("bg_color", "#FFFFFF"))
        self.bg_color.setPlaceholderText("#FFFFFF")
        self.brand_text = QLineEdit(cfg.get("brand_text", ""))
        self.brand_text.setPlaceholderText("행사명·문구 (예: 2026 SEOUL POPUP)")
        self.brand_text_color = QLineEdit(cfg.get("brand_text_color", "#222222"))
        self.brand_text_color.setPlaceholderText("#222222")
        # 문구 위치 9방향 + 미세 조정
        self.brand_text_pos = NoWheelComboBox()
        self._text_pos_map = {
            "왼쪽 위": "top-left", "가운데 위": "top-center", "오른쪽 위": "top-right",
            "왼쪽 중앙": "middle-left", "정중앙": "center", "오른쪽 중앙": "middle-right",
            "왼쪽 아래": "bottom-left", "가운데 아래": "bottom-center", "오른쪽 아래": "bottom-right"}
        self.brand_text_pos.addItems(list(self._text_pos_map.keys()))
        _cur = cfg.get("brand_text_pos", "bottom-center")
        _cur = {"bottom": "bottom-center", "top": "top-center"}.get(_cur, _cur)
        for k, vv in self._text_pos_map.items():
            if vv == _cur:
                self.brand_text_pos.setCurrentText(k); break
        self.brand_text_dx = NoWheelSpinBox(); self.brand_text_dx.setRange(-40, 40)
        self.brand_text_dx.setValue(cfg.get("brand_text_dx", 0)); self.brand_text_dx.setSuffix(" % 가로")
        self.brand_text_dy = NoWheelSpinBox(); self.brand_text_dy.setRange(-40, 40)
        self.brand_text_dy.setValue(cfg.get("brand_text_dy", 0)); self.brand_text_dy.setSuffix(" % 세로")
        # 글자 크기 — 포인트 단위(출력 크기에 맞춰 자동 환산)
        self.brand_text_pt = NoWheelSpinBox(); self.brand_text_pt.setRange(8, 200)
        self.brand_text_pt.setValue(cfg.get("brand_text_pt", 40))
        self.brand_text_pt.setSuffix(" pt")
        # 촬영 전 보정
        # 보정은 가로 슬라이더 — 드래그하며 미리보기를 바로 보는 게 수치 입력보다 직관적
        adj = cfg.get("adjust", {}) or {}
        def _slider(lo, hi, val):
            s = NoWheelSlider(); s.setRange(lo, hi); s.setValue(int(val)); return s
        self.adj_bright = _slider(-100, 100, adj.get("brightness", 0))
        self.adj_contrast = _slider(-100, 100, adj.get("contrast", 0))
        self.adj_sat = _slider(-100, 100, adj.get("saturation", 0))
        self.adj_sharp = _slider(0, 100, adj.get("sharpness", 0))
        self.brand_date_chk = QCheckBox("촬영 날짜 함께 표시")
        self.brand_date_chk.setChecked(cfg.get("brand_show_date", False))
        self.logo_path = QLineEdit(cfg.get("logo_path", ""))
        self.logo_path.setPlaceholderText("로고 PNG (투명 배경 권장)")
        self.logo_scale = NoWheelSpinBox(); self.logo_scale.setRange(3, 50)
        self.logo_scale.setValue(cfg.get("logo_scale", 15))
        self.logo_scale.setSuffix(" %")
        self.logo_pos = NoWheelComboBox()
        self._logo_pos_map = {"오른쪽 아래": "bottom-right", "왼쪽 아래": "bottom-left",
                              "오른쪽 위": "top-right", "왼쪽 위": "top-left"}
        self.logo_pos.addItems(list(self._logo_pos_map.keys()))
        for k, v in self._logo_pos_map.items():
            if v == cfg.get("logo_pos", "bottom-right"):
                self.logo_pos.setCurrentText(k)
                break

    def _build_prefs_dialog(self) -> QDialog:
        dlg = QDialog(self)
        dlg.setWindowTitle("환경설정")
        dlg.setModal(False)
        dlg.setMinimumWidth(900)
        # 최대화 허용 — 창을 키우면 미리보기도 함께 커진다(보정 확인이 쉬워짐)
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowMaximizeButtonHint)
        dlg.installEventFilter(self)   # 크기 변경 감지 → 미리보기 다시 그림(아래 eventFilter)
        dlg.setStyleSheet(
            f"QDialog{{background:{INK};}} QScrollArea{{border:none;background:transparent;}}"
            f"QTabWidget::pane{{border:none;background:transparent;}}"
            f"QTabBar{{background:transparent;}}"
            f"QTabBar::tab{{background:transparent;color:{MUTED};padding:12px 22px;margin-right:4px;"
            f"font-size:17px;font-weight:600;border-bottom:2px solid transparent;}}"
            f"QTabBar::tab:selected{{color:{TEXT};border-bottom:2px solid {GOLD};}}"
            f"QTabBar::tab:hover{{color:{TEXT};}}")
        outer = QVBoxLayout(dlg); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        # ── 헤더(고정) ──
        head = QWidget(); head.setStyleSheet(f"background:{SURFACE}; border-bottom:1px solid {LINE};")
        hv = QVBoxLayout(head); hv.setContentsMargins(26, 18, 26, 0); hv.setSpacing(3)
        title = QLabel("환경설정"); title.setStyleSheet(f"color:{TEXT}; font-size:26px; font-weight:800;")
        hv.addWidget(title)
        sub = QLabel("운영자용 상세 설정 — 손님에게는 보이지 않습니다")
        sub.setStyleSheet(f"color:{MUTED}; font-size:15px;"); hv.addWidget(sub)
        outer.addWidget(head)

        # ── 상단 메뉴(탭) ──
        from PyQt5.QtWidgets import QTabWidget
        tabs = QTabWidget(); tabs.setDocumentMode(True)
        outer.addWidget(tabs, 1)

        # 탭 1: 일반 설정(스크롤)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget(); content.setStyleSheet("background:transparent;")
        scroll.setWidget(content)
        tabs.addTab(scroll, "일반 설정")
        v = QVBoxLayout(content); v.setContentsMargins(26, 20, 26, 12); v.setSpacing(8)

        def section(name, target=None):
            tgt = target if target is not None else v
            tgt.addWidget(_eyebrow(name)); g = QGridLayout(); g.setVerticalSpacing(10)
            g.setHorizontalSpacing(12); tgt.addLayout(g); return g

        # 카메라
        g = section("카메라")
        g.addWidget(_flabel("백엔드"), 0, 0); g.addWidget(self.backend_box, 0, 1)
        g.addWidget(_flabel("장치"), 1, 0)
        drow = QHBoxLayout(); drow.addWidget(self.device_combo, 1)
        sbtn = QPushButton(); sbtn.setIcon(icons.icon("search", MUTED, 16)); sbtn.setToolTip("카메라 검색")
        sbtn.clicked.connect(self.camera_search_requested.emit); drow.addWidget(sbtn)
        g.addLayout(drow, 1, 1)
        g.addWidget(_flabel("촬영 해상도"), 2, 0); g.addWidget(self.res_box, 2, 1)
        g.setColumnStretch(1, 1)
        v.addSpacing(12)

        # 촬영
        g = section("촬영")
        g.addWidget(_flabel("카운트다운(초)"), 0, 0); g.addWidget(self.countdown, 0, 1)
        g.addWidget(_flabel("준비 화면 자동 복귀"), 1, 0); g.addWidget(self.ready_timeout, 1, 1)
        rnote = QLabel("손님이 준비 화면까지 왔다가 그냥 가면, 이 시간 뒤 대기 화면으로 돌아갑니다.")
        rnote.setStyleSheet(f"color:{MUTED}; font-size:14px;"); rnote.setWordWrap(True)
        g.addWidget(rnote, 2, 0, 1, 2)
        g.addWidget(_flabel("촬영 중 방치 시 취소"), 3, 0); g.addWidget(self.abandon_timeout, 3, 1)
        anote = QLabel("컷을 찍다가 손님이 가버리면, 이 시간 뒤 찍은 컷을 취소하고 대기 화면으로 돌아갑니다.\n"
                       "(설정 시간의 절반이 남으면 손님 화면에 남은 초를 예고합니다)")
        anote.setStyleSheet(f"color:{MUTED}; font-size:14px;"); anote.setWordWrap(True)
        g.addWidget(anote, 4, 0, 1, 2)
        g.addWidget(self.flash_chk, 5, 0, 1, 2)
        g.addWidget(self.sound_chk, 6, 0, 1, 2)
        g.addWidget(self.mirror_chk, 7, 0, 1, 2)
        g.setColumnStretch(1, 1)
        v.addSpacing(12)

        # 완성 · 공유
        g = section("완성 · 공유")
        g.addWidget(_flabel("QR 안내 표시(초)"), 0, 0); g.addWidget(self.qr_delay, 0, 1)
        g.addWidget(_flabel("완성 후 자동 복귀"), 1, 0); g.addWidget(self.autoreturn, 1, 1)
        g.addWidget(self.reveal_chk, 2, 0, 1, 2)
        g.addWidget(_flabel("연출 길이"), 3, 0); g.addWidget(self.reveal_sec, 3, 1)
        g.addWidget(_flabel("전달 방식"), 4, 0)
        deliv = QLabel("기본: 같은 WiFi 로컬 전달 (사진이 행사장 밖으로 안 나감)")
        deliv.setStyleSheet(f"color:{OK_GREEN}; font-size:15px;")
        g.addWidget(deliv, 4, 1)
        g.addWidget(self.cloud_chk, 5, 0, 1, 2)
        warn = QLabel("⚠ 클라우드를 켜면 손님 사진이 외부 서버로 업로드됩니다(개인정보 주의).")
        warn.setStyleSheet("color:#FF8A9B; font-size:14px;"); warn.setWordWrap(True)
        g.addWidget(warn, 6, 0, 1, 2)
        g.addWidget(_flabel("공유 포트"), 7, 0); g.addWidget(self.share_port, 7, 1)
        pnote2 = QLabel("포트를 고정해 두면 앱을 다시 켜도 이전에 나눠준 QR이 계속 동작합니다.")
        pnote2.setStyleSheet(f"color:{MUTED}; font-size:14px;"); pnote2.setWordWrap(True)
        g.addWidget(pnote2, 8, 0, 1, 2)
        g.addWidget(self.gif_chk, 9, 0, 1, 2)
        g.addWidget(_flabel("움짤 형식"), 10, 0); g.addWidget(self.gif_format, 10, 1)
        g.addWidget(_flabel("움짤 크기"), 11, 0); g.addWidget(self.gif_width, 11, 1)
        g.addWidget(_flabel("움짤 부드러움"), 12, 0); g.addWidget(self.gif_fps, 12, 1)
        gnote = QLabel("촬영 순간의 짧은 영상으로 움직이는 4컷을 만들어 완성 화면에 QR로 함께 제공합니다."
                       " (전부 로컬 처리 · 인스타 업로드는 MP4 권장)")
        gnote.setStyleSheet(f"color:{MUTED}; font-size:14px;"); gnote.setWordWrap(True)
        g.addWidget(gnote, 13, 0, 1, 2)
        g.setColumnStretch(1, 1)
        v.addSpacing(12)

        # 손님 연결 안내 (WiFi 접속 QR)
        g = section("손님 연결 안내 (WiFi QR)")
        g.addWidget(_flabel("방식"), 0, 0); g.addWidget(self.wifi_mode_box, 0, 1)
        g.addWidget(_flabel("WiFi 이름"), 1, 0)
        wrow = QHBoxLayout(); wrow.addWidget(self.wifi_ssid, 1)
        wauto = QPushButton("자동 채우기")
        wauto.setToolTip("현재 WiFi 이름 / 모바일 핫스팟의 이름·비밀번호를 자동 입력")
        wauto.clicked.connect(self._autofill_dispatch); wrow.addWidget(wauto)
        g.addLayout(wrow, 1, 1)
        g.addWidget(_flabel("WiFi 비밀번호"), 2, 0); g.addWidget(self.wifi_pw, 2, 1)
        wnote = QLabel("완성 화면에 'WiFi 연결 QR'을 함께 표시 → 손님이 스캔 한 번으로 접속.\n"
                       "⚠ 개인/매장 WiFi 대신 손님 전용 WiFi나 모바일 핫스팟을 권장(비번이 노출됨).")
        wnote.setStyleSheet(f"color:{MUTED}; font-size:14px;"); wnote.setWordWrap(True)
        g.addWidget(wnote, 3, 0, 1, 2)
        g.setColumnStretch(1, 1)
        v.addSpacing(12)

        # 저장 · 템플릿
        g = section("저장 · 화질 · 템플릿")
        g.addWidget(_flabel("저장 경로"), 0, 0)
        srow = QHBoxLayout(); srow.addWidget(self.save_edit, 1)
        sb = QPushButton(); sb.setIcon(icons.icon("folder", MUTED, 16)); sb.setToolTip("찾기")
        sb.clicked.connect(self._pick_save); srow.addWidget(sb)
        g.addLayout(srow, 0, 1)
        g.addWidget(_flabel("저장 화질"), 1, 0); g.addWidget(self.quality_box, 1, 1)
        g.addWidget(_flabel("템플릿 PNG"), 2, 0)
        trow = QHBoxLayout(); trow.addWidget(self.template_edit, 1)
        tb = QPushButton(); tb.setIcon(icons.icon("folder", MUTED, 16)); tb.setToolTip("찾기")
        tb.clicked.connect(self._pick_template); trow.addWidget(tb)
        g.addLayout(trow, 2, 1)
        g.addWidget(self.keepcuts_chk, 3, 0, 1, 2)
        g.setColumnStretch(1, 1)
        v.addSpacing(12)

        # ══ 탭 2: 브랜딩 · 색감 (좌 컨트롤 / 우 라이브 미리보기) ══
        brand_tab = QWidget()
        bh = QHBoxLayout(brand_tab); bh.setContentsMargins(0, 0, 0, 0); bh.setSpacing(0)
        bscroll = QScrollArea(); bscroll.setWidgetResizable(True)
        bscroll.setFrameShape(QFrame.NoFrame)
        bscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        bcontent = QWidget(); bcontent.setStyleSheet("background:transparent;")
        bscroll.setWidget(bcontent); bscroll.setFixedWidth(500)
        bv = QVBoxLayout(bcontent); bv.setContentsMargins(26, 20, 20, 16); bv.setSpacing(8)
        bh.addWidget(bscroll)
        # 우측 미리보기 패널
        ppane = QWidget(); ppane.setStyleSheet(f"background:{SURFACE}; border-left:1px solid {LINE};")
        pv2 = QVBoxLayout(ppane); pv2.setContentsMargins(22, 20, 22, 20); pv2.setSpacing(10)
        pv2.addWidget(_eyebrow("미리보기 (값 바꾸면 즉시 반영)"))
        # 완성 화면과 동일하게 — 흰 테두리 없이 결과물 그대로(보이는 것 = 받는 파일)
        pframe = QWidget(); pframe.setStyleSheet("background:transparent;")
        shadow(pframe, blur=30, dy=8, alpha=120)
        self._brand_frame = pframe
        pframe.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        pfl = QVBoxLayout(pframe); pfl.setContentsMargins(0, 0, 0, 0)
        self.brand_preview = QLabel("미리보기 준비 중…")
        self.brand_preview.setAlignment(Qt.AlignCenter)
        self.brand_preview.setStyleSheet("background:transparent; color:#888; font-size:15px;")
        # 화면 높이에 맞춰 미리보기를 최대한 크게(작은 화면에서도 잘리지 않게)
        _scr = QApplication.primaryScreen().availableGeometry()
        self._preview_box = (560, max(320, min(600, _scr.height() - 330)))
        self.brand_preview.setMinimumSize(360, 300)
        pfl.addWidget(self.brand_preview)
        pv2.addWidget(pframe, 0, Qt.AlignCenter)
        pnote = QLabel("사진 자리는 비워둔 '사진 없는 완성본'입니다. 실제 출력과 같은 비율로 보여줍니다.")
        pnote.setStyleSheet(f"color:{MUTED}; font-size:14px;"); pnote.setWordWrap(True)
        pv2.addWidget(pnote)
        # 색감·보정은 실제 사진이 있어야 확인 가능 → 테스트 촬영 1장으로 4컷을 채운다
        trow = QHBoxLayout(); trow.setSpacing(8)
        self.testshot_btn = QPushButton("  테스트 촬영")
        self.testshot_btn.setIcon(icons.icon("camera", TEXT, 18)); self.testshot_btn.setMinimumHeight(44)
        self.testshot_btn.setToolTip("지금 카메라 화면을 1장 찍어 미리보기 4컷에 채웁니다")
        self.testshot_btn.clicked.connect(self._take_test_shot)
        self.clearshot_btn = QPushButton("사진 없이 보기")
        self.clearshot_btn.setMinimumHeight(44)
        self.clearshot_btn.clicked.connect(self._clear_test_shot)
        # 색감·보정은 한 컷을 크게 봐야 판단이 된다 → 1장만 크게 보기 토글
        self.single_btn = QPushButton("  사진 1장만 크게")
        self.single_btn.setIcon(icons.icon("maximize", TEXT, 17)); self.single_btn.setMinimumHeight(44)
        self.single_btn.setToolTip("4컷 대신 사진 한 장을 크게 보여줍니다(색감·보정 확인용)")
        self.single_btn.setCheckable(True)
        self.single_btn.toggled.connect(self._toggle_single_view)
        trow.addWidget(self.testshot_btn); trow.addWidget(self.clearshot_btn)
        trow.addWidget(self.single_btn); trow.addStretch(1)
        pv2.addLayout(trow)
        pv2.addStretch(1)
        self._preview_pane = ppane
        # 내용(이미지)이 커져도 패널이 창을 밀지 않게 — 되먹임으로 계속 커지는 것 방지
        ppane.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        ppane.setMinimumSize(200, 200)
        bh.addWidget(ppane, 1)
        tabs.addTab(brand_tab, "브랜딩 · 색감")

        g = section("브랜딩 · 색감", bv)
        g.addWidget(_flabel("사진 색감"), 0, 0); g.addWidget(self.tone_box, 0, 1)
        g.addWidget(_flabel("배경(프레임) 색"), 1, 0)
        bgrow = QHBoxLayout(); bgrow.setSpacing(8); bgrow.addWidget(self.bg_color, 1)
        bgbtn = self._swatch_button(self.bg_color, "배경(프레임) 색")
        bgrow.addWidget(bgbtn); g.addLayout(bgrow, 1, 1)
        g.addWidget(_flabel("문구"), 2, 0); g.addWidget(self.brand_text, 2, 1)
        g.addWidget(_flabel("문구 색"), 3, 0)
        tcrow = QHBoxLayout(); tcrow.setSpacing(8); tcrow.addWidget(self.brand_text_color, 1)
        tcbtn = self._swatch_button(self.brand_text_color, "문구 색")
        tcrow.addWidget(tcbtn); g.addLayout(tcrow, 3, 1)
        g.addWidget(_flabel("문구 위치"), 4, 0); g.addWidget(self.brand_text_pos, 4, 1)
        g.addWidget(_flabel("문구 미세 이동"), 5, 0)
        drow2 = QHBoxLayout(); drow2.addWidget(self.brand_text_dx); drow2.addWidget(self.brand_text_dy)
        g.addLayout(drow2, 5, 1)
        g.addWidget(_flabel("문구 크기"), 6, 0); g.addWidget(self.brand_text_pt, 6, 1)
        g.addWidget(self.brand_date_chk, 7, 0, 1, 2)
        g.addWidget(_flabel("로고 PNG"), 8, 0)
        lrow = QHBoxLayout(); lrow.addWidget(self.logo_path, 1)
        lbtn = QPushButton(); lbtn.setIcon(icons.icon("folder", MUTED, 16)); lbtn.setToolTip("찾기")
        lbtn.clicked.connect(self._pick_logo); lrow.addWidget(lbtn)
        g.addLayout(lrow, 8, 1)
        g.addWidget(_flabel("로고 크기"), 9, 0); g.addWidget(self.logo_scale, 9, 1)
        g.addWidget(_flabel("로고 위치"), 10, 0); g.addWidget(self.logo_pos, 10, 1)
        bnote = QLabel("배경색·문구·로고는 템플릿 PNG 없이도 적용됩니다.")
        bnote.setStyleSheet(f"color:{MUTED}; font-size:14px;"); bnote.setWordWrap(True)
        g.addWidget(bnote, 11, 0, 1, 2)
        g.setColumnStretch(1, 1)

        # 촬영 전 보정 — 라벨 / 슬라이더 / 값 (컴팩트 한 줄)
        g2 = section("촬영 전 보정", bv)
        for r, (name, sl) in enumerate((("밝기", self.adj_bright), ("대비", self.adj_contrast),
                                        ("채도", self.adj_sat), ("선명도", self.adj_sharp))):
            lab = QLabel(name); lab.setFixedWidth(52)
            lab.setStyleSheet(f"color:{MUTED}; font-size:15px; font-weight:600;")
            val = QLabel(str(sl.value())); val.setFixedWidth(42)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet(f"color:{TEXT}; font-size:15px; font-weight:700;")
            sl.valueChanged.connect(lambda v, _l=val: _l.setText(str(v)))
            row = QHBoxLayout(); row.setSpacing(8)
            row.addWidget(lab); row.addWidget(sl, 1); row.addWidget(val)
            g2.addLayout(row, r, 0, 1, 2)
        rst = QPushButton("보정 초기화"); rst.setMinimumHeight(38)
        rst.clicked.connect(self._reset_adjust)
        g2.addWidget(rst, 4, 0, 1, 2)
        anote2 = QLabel("0이면 보정 없음. 라이브 미리보기·촬영 결과에 똑같이 적용됩니다.")
        anote2.setStyleSheet(f"color:{MUTED}; font-size:14px;"); anote2.setWordWrap(True)
        g2.addWidget(anote2, 5, 0, 1, 2)
        g2.setColumnStretch(1, 1)
        bv.addStretch(1)
        # 값이 바뀌면 즉시 미리보기 갱신(디바운스)
        for wdg in (self.tone_box, self.brand_text_pos, self.logo_pos):
            wdg.currentIndexChanged.connect(self._queue_brand_preview)
        for wdg in (self.bg_color, self.brand_text, self.brand_text_color, self.logo_path):
            wdg.textChanged.connect(self._queue_brand_preview)
        for wdg in (self.brand_text_pt, self.logo_scale, self.brand_text_dx, self.brand_text_dy,
                    self.adj_bright, self.adj_contrast, self.adj_sat, self.adj_sharp):
            wdg.valueChanged.connect(self._queue_brand_preview)
        self.brand_date_chk.toggled.connect(self._queue_brand_preview)
        tabs.currentChanged.connect(
            lambda i: self._queue_brand_preview() if i == 1 else None)

        # ══ 탭 3: 손님 받기 페이지 ══
        tabs.addTab(self._build_page_tab(section), "손님 받기 페이지")

        # 트리거
        g = section("트리거 키")
        g.addWidget(_flabel("촬영 시작/다음 컷 키"), 0, 0); g.addWidget(self.trigger_btn, 0, 1)
        g.setColumnStretch(1, 1)
        v.addStretch(1)

        # 닫기 버튼 — 스크롤 밖(항상 하단 고정)에 둔다.
        footer = QWidget(); footer.setStyleSheet(f"background:{INK}; border-top:1px solid {LINE};")
        frow = QHBoxLayout(footer); frow.setContentsMargins(26, 12, 26, 14); frow.setSpacing(10)
        close = QPushButton("  닫기"); close.setObjectName("primary")
        close.setIcon(icons.icon("check", "#FFFFFF", 18)); close.setMinimumHeight(46)
        close.clicked.connect(dlg.accept)
        frow.addStretch(1); frow.addWidget(close)
        outer.addWidget(footer)

        # 화면보다 크지 않게 초기 크기 지정(내용은 스크롤로 접근)
        scr = QApplication.primaryScreen().availableGeometry()
        dlg.resize(min(1240, scr.width() - 60), min(920, scr.height() - 60))
        dlg.finished.connect(lambda _: self._refresh_info())  # 닫으면 구성요약 갱신
        return dlg

    # ── 손님 받기 페이지 탭 ───────────────────────────────────────────
    def _build_page_tab(self, section) -> QWidget:
        """QR로 접속한 손님이 보는 페이지 설정 + 실제 모습 미리보기."""
        tab = QWidget()
        h = QHBoxLayout(tab); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget(); content.setStyleSheet("background:transparent;")
        scroll.setWidget(content); scroll.setFixedWidth(500)
        v = QVBoxLayout(content); v.setContentsMargins(26, 20, 20, 16); v.setSpacing(8)
        h.addWidget(scroll)

        g = section("손님 받기 페이지", v)
        g.addWidget(_flabel("행사 문구"), 0, 0); g.addWidget(self.page_title, 0, 1)
        g.addWidget(_flabel("배경색"), 1, 0)
        r1 = QHBoxLayout(); r1.setSpacing(8); r1.addWidget(self.page_bg, 1)
        r1.addWidget(self._swatch_button(self.page_bg, "페이지 배경색")); g.addLayout(r1, 1, 1)
        g.addWidget(_flabel("글자색"), 2, 0)
        r2 = QHBoxLayout(); r2.setSpacing(8); r2.addWidget(self.page_fg, 1)
        r2.addWidget(self._swatch_button(self.page_fg, "페이지 글자색")); g.addLayout(r2, 2, 1)
        g.addWidget(_flabel("로고 PNG"), 3, 0)
        r3 = QHBoxLayout(); r3.addWidget(self.page_logo, 1)
        lb = QPushButton(); lb.setIcon(icons.icon("folder", MUTED, 16)); lb.setToolTip("찾기")
        lb.clicked.connect(lambda: self._pick_into(self.page_logo)); r3.addWidget(lb)
        g.addLayout(r3, 3, 1)
        note = QLabel("손님이 QR을 스캔하면 보이는 화면입니다. 여기서 사진과 움짤을 함께 저장합니다.\n"
                      "사진에 넣는 브랜딩과는 별개로 지정할 수 있습니다.")
        note.setStyleSheet(f"color:{MUTED}; font-size:14px;"); note.setWordWrap(True)
        g.addWidget(note, 4, 0, 1, 2)
        g.setColumnStretch(1, 1)
        v.addStretch(1)

        # ── 우측: 휴대폰 모양 미리보기 ──
        pane = QWidget(); pane.setStyleSheet(f"background:{SURFACE}; border-left:1px solid {LINE};")
        pane.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        pane.setMinimumSize(200, 200)
        pv = QVBoxLayout(pane); pv.setContentsMargins(22, 20, 22, 20); pv.setSpacing(10)
        pv.addWidget(_eyebrow("손님 화면 미리보기"))
        phone = QWidget(); phone.setFixedWidth(330)
        phone.setObjectName("phone")
        shadow(phone, blur=34, dy=10, alpha=140)
        self._page_phone = phone
        pl = QVBoxLayout(phone); pl.setContentsMargins(20, 22, 20, 22); pl.setSpacing(12)
        self._pg_logo = QLabel(); self._pg_logo.setAlignment(Qt.AlignCenter); self._pg_logo.hide()
        pl.addWidget(self._pg_logo)
        self._pg_title = QLabel("사진이 준비되었어요")
        self._pg_title.setAlignment(Qt.AlignCenter); self._pg_title.setWordWrap(True)
        pl.addWidget(self._pg_title)
        self._pg_sub = QLabel("아래에서 저장하세요")
        self._pg_sub.setAlignment(Qt.AlignCenter)
        pl.addWidget(self._pg_sub)
        self._pg_card = QWidget(); self._pg_card.setObjectName("pgcard")
        cl = QVBoxLayout(self._pg_card); cl.setContentsMargins(12, 12, 12, 12); cl.setSpacing(10)
        self._pg_shot = QLabel(); self._pg_shot.setFixedHeight(96)
        self._pg_shot.setStyleSheet("background:#E2E5EA; border-radius:8px;")
        cl.addWidget(self._pg_shot)
        self._pg_btn = QLabel("사진 저장하기"); self._pg_btn.setAlignment(Qt.AlignCenter)
        self._pg_btn.setStyleSheet("background:#4C7DFF; color:white; border-radius:10px;"
                                   "padding:11px 0; font-size:15px; font-weight:700;")
        cl.addWidget(self._pg_btn)
        pl.addWidget(self._pg_card)
        self._pg_card2 = QWidget(); self._pg_card2.setObjectName("pgcard")
        c2 = QVBoxLayout(self._pg_card2); c2.setContentsMargins(12, 12, 12, 12); c2.setSpacing(10)
        self._pg_tag = QLabel("움직이는 4컷")
        c2.addWidget(self._pg_tag)
        self._pg_shot2 = QLabel(); self._pg_shot2.setFixedHeight(72)
        self._pg_shot2.setStyleSheet("background:#E2E5EA; border-radius:8px;")
        c2.addWidget(self._pg_shot2)
        self._pg_btn2 = QLabel("움짤 저장하기"); self._pg_btn2.setAlignment(Qt.AlignCenter)
        c2.addWidget(self._pg_btn2)
        pl.addWidget(self._pg_card2)
        self._pg_foot = QLabel("부스 운영 중에만 받을 수 있어요")
        self._pg_foot.setAlignment(Qt.AlignCenter); self._pg_foot.setWordWrap(True)
        pl.addWidget(self._pg_foot)
        pv.addWidget(phone, 0, Qt.AlignHCenter)
        pv.addStretch(1)
        h.addWidget(pane, 1)

        for w in (self.page_title, self.page_bg, self.page_fg, self.page_logo):
            w.textChanged.connect(self._render_page_preview)
        self._render_page_preview()
        return tab

    def _render_page_preview(self):
        """설정한 색·문구·로고가 손님 화면에 어떻게 보이는지 즉시 반영."""
        from core.share_page import _is_dark
        bg = self.page_bg.text().strip() or "#0B0E13"
        fg = self.page_fg.text().strip() or "#EEF1F7"
        dark = _is_dark(bg)
        muted = "rgba(255,255,255,0.55)" if dark else "rgba(0,0,0,0.5)"
        card = "rgba(255,255,255,0.07)" if dark else "rgba(0,0,0,0.05)"
        line = "rgba(255,255,255,0.14)" if dark else "rgba(0,0,0,0.12)"
        self._page_phone.setStyleSheet(
            f"#phone{{background:{bg}; border:1px solid {line}; border-radius:18px;}}"
            f"#pgcard{{background:{card}; border:1px solid {line}; border-radius:14px;}}")
        self._pg_title.setText(self.page_title.text().strip() or "사진이 준비되었어요")
        self._pg_title.setStyleSheet(f"color:{fg}; font-size:19px; font-weight:800;")
        self._pg_sub.setStyleSheet(f"color:{muted}; font-size:13px;")
        self._pg_tag.setStyleSheet(f"color:{muted}; font-size:12px; font-weight:700;")
        self._pg_btn2.setStyleSheet(f"color:{fg}; border:1px solid {line}; border-radius:10px;"
                                    "padding:10px 0; font-size:14px; font-weight:700;")
        self._pg_foot.setStyleSheet(f"color:{muted}; font-size:12px;")
        p = self.page_logo.text().strip()
        pm = QPixmap(p) if p else QPixmap()
        if not pm.isNull():
            self._pg_logo.setPixmap(pm.scaled(160, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._pg_logo.show()
        else:
            self._pg_logo.hide()

    def open_settings(self):
        self.prefs.show(); self.prefs.raise_(); self.prefs.activateWindow()

    def _refresh_info(self):
        from pathlib import Path as _P
        def onoff(b):
            return "켜짐" if b else "꺼짐"
        try:
            r = self._info_rows
            r["layout"].setText(self.layout_box.currentData() or self.layout_box.currentText())
            r["res"].setText(self.res_box.currentText().split(" (")[0])
            r["quality"].setText(self.quality_box.currentText().split(" (")[0])
            r["tone"].setText(self.tone_box.currentText())
            bits = []
            if self.brand_text.text().strip():
                bits.append("문구")
            if self.brand_date_chk.isChecked():
                bits.append("날짜")
            if self.logo_path.text().strip():
                bits.append("로고")
            r["brand"].setText(" · ".join(bits) if bits else "없음")
            r["countdown"].setText(f"{self.countdown.value()}초")
            r["cuts"].setText("4 컷")
            r["flash"].setText(onoff(self.flash_chk.isChecked()))
            r["sound"].setText(onoff(self.sound_chk.isChecked()))
            r["mirror"].setText(onoff(self.mirror_chk.isChecked()))
            r["delivery"].setText("클라우드" if self.cloud_chk.isChecked() else "로컬(WiFi)")
            wmode = ["표시 안 함", "현재 WiFi", "모바일 핫스팟"][self.wifi_mode_box.currentIndex()]
            ssid = self.wifi_ssid.text().strip()
            r["wifi"].setText(wmode if self.wifi_mode_box.currentIndex() == 0
                              else f"{wmode} · {ssid or '이름 미설정'}")
            rt = self.ready_timeout.value()
            r["readyto"].setText("끔" if rt == 0 else f"{rt}초")
            at = self.abandon_timeout.value()
            r["abandonto"].setText("끔" if at == 0 else f"{at}초")
            ar = self.autoreturn.value()
            r["autoreturn"].setText("수동" if ar == 0 else f"{ar}초")
            sp = self.save_edit.text().strip() or "results"
            r["save"].setText(_P(sp).name or sp)
            r["trigger"].setText(self.trigger_btn.key_name or "Space")
        except Exception:  # noqa: BLE001
            pass

    def set_camera_error(self, msg: str):
        """카메라가 왜 안 붙는지 화면에 그대로 띄운다.

        ⚠️ 예전엔 실패해도 "카메라를 자동 연결하고 있어요…"만 계속 떠서, 실제로 원인을
        찾는 데 오래 걸렸다(다른 프로그램이 장치를 물고 있던 경우). 조용한 실패 금지.
        """
        if not msg:
            return
        self.preview.setPixmap(QPixmap())        # 옛 프레임이 남아 정상처럼 보이지 않게
        self.preview.setText("⚠ " + msg)
        self.preview.setStyleSheet(
            f"background:#2A1A12; border:1px solid #7A4A2E; border-radius:12px;"
            f"color:#FFD98A; font-size:17px; font-weight:600; padding:14px;")
        self.cam_status.setText("● 연결 실패")
        self.cam_status.setStyleSheet("color:#FFD98A; font-size:15px; font-weight:700;")

    def set_guest_addr(self, url: str, kind: str):
        """손님이 접속할 주소를 요약표에 보여준다(자동 판정 결과).

        ⚠️ 폰은 유선을 못 꽂는다 — 후보가 유선뿐이면 주소를 띄우는 것보다 **핫스팟을 켜라고
        말해 주는 편**이 맞다. 그 상태로 QR을 나눠주면 손님은 열 수 없다.
        """
        row = self._info_rows.get("guestaddr")
        if row is None:
            return
        ip = url.replace("http://", "").rstrip("/")
        # 운영 정책(오너 2026-08-09): **유선이든 WiFi든 핫스팟을 켜는 것이 기본.**
        # 장소 WiFi 는 비밀번호·게스트망 격리 때문에 손님이 못 붙는 일이 잦다.
        warn = kind != "핫스팟"
        if kind == "없음":
            row.setText("연결 없음 · 핫스팟/공유기 필요")
        elif kind == "유선":
            row.setText("유선뿐 · 핫스팟을 켜세요")      # 폰은 유선을 못 꽂는다
        elif kind == "WiFi":
            row.setText(f"{ip} · WiFi(핫스팟 권장)")
        else:
            row.setText(f"{ip} · {kind}")
        row.setStyleSheet(
            f"color:{'#FFD98A' if warn else TEXT}; font-size:15px; font-weight:600;")
        row.setToolTip("\n".join([
            "권장: 이 PC의 모바일 핫스팟을 켜고 손님을 거기 붙입니다.",
            "  장소 WiFi 는 비밀번호·게스트망 격리 때문에 손님이 못 붙는 일이 잦습니다.",
            "· 유선/WiFi 로 인터넷이 있으면 핫스팟이 켜집니다(그 연결을 공유).",
            "· 인터넷이 하나도 없으면 이 PC 핫스팟은 켜지지 않습니다.",
            "  → 인터넷 회선이 없는 빈 공유기라도 좋으니 PC·손님을 같은 공유기에 붙이세요.",
            "  → 또는 운영자 폰 핫스팟에 PC·손님을 함께 연결(기기 간 통신 차단 여부 확인).",
            "※ 부스 시작 전 폰으로 QR 을 한 번 찍어 실접속을 확인하세요.",
        ]) if warn else "손님이 이 핫스팟에 붙어 사진을 받습니다.")

    def _on_camera_changed(self, *_):
        if not self._suppress_reconnect:
            self.test_camera_requested.emit()  # 카메라 선택 바뀌면 자동 재연결

    def _sync_hint(self):
        # F3 안내는 필수 — 화면이 반대 모니터에 떴을 때 이 문구가 없으면 손쓸 방법을 모른다
        self.hint2.setText(
            f"‘{self.trigger_key}’ 키 또는 ‘촬영 시작’으로 시작   ·   F3 모니터 바꾸기   ·   F2 손님 화면")

    def showEvent(self, e):
        self._ready_at = time.monotonic() + 0.6
        self._sync_hint()
        super().showEvent(e)

    def eventFilter(self, obj, ev):
        # 설정 창 크기가 바뀌면(최대화 포함) 미리보기를 그 크기에 맞춰 다시 그린다
        if ev.type() == QEvent.Resize and obj is getattr(self, "prefs", None):
            self._queue_brand_preview()
            return False
        if ev.type() == QEvent.KeyPress and self.isVisible() and not ev.isAutoRepeat():
            if self.trigger_btn._capturing:
                return False
            if self.prefs.isVisible():   # 설정 창이 열려 있으면 트리거로 촬영 시작 안 함
                return False
            name = QKeySequence(ev.key()).toString()
            if name and name == QKeySequence(self.trigger_key).toString():
                if time.monotonic() >= self._ready_at:
                    self.start_requested.emit()
                return True
            if ev.key() in (Qt.Key_Left, Qt.Key_Right) and self._arrows_free():
                if self._step_user_layout(-1 if ev.key() == Qt.Key_Left else 1):
                    return True
        return super().eventFilter(obj, ev)

    def _arrows_free(self, focused=None):
        """좌우 방향키를 레이아웃 전환에 써도 되는 상황인가.

        ⚠️ 같은 키가 이미 **슬롯 미세이동**(칸 선택 후 1px/Shift 10px)과 텍스트 입력에 쓰인다.
        그쪽이 먼저다 — 칸을 고른 채 편집 중이거나 입력칸에 커서가 있으면 손대지 않는다.
        """
        from PyQt5.QtWidgets import QLineEdit, QSpinBox, QComboBox, QAbstractSpinBox
        if self.editor.sel is not None:
            return False        # 칸을 고른 상태 = 미세이동 중(빈 곳을 클릭해 선택을 풀면 전환된다)
        w = focused if focused is not None else QApplication.focusWidget()
        return not isinstance(w, (QLineEdit, QSpinBox, QAbstractSpinBox, QComboBox))

    def _step_user_layout(self, d):
        """좌우 방향키 — **내가 등록한 레이아웃만** 순환한다(예시는 건너뛴다).

        현장에서 쓰는 건 자기가 만든 디자인이지 예시가 아니다. 예시가 사이에 끼면
        손님 앞에서 엉뚱한 화면이 뜬다. 등록한 레이아웃이 없으면 아무 일도 하지 않는다.
        """
        names = [u["name"] for u in self.user_layouts]
        if not names:
            return False
        cur = getattr(self, "_active_layout", None)
        if cur in names:
            nxt = names[(names.index(cur) + d) % len(names)]
        else:                                 # 지금이 예시면 바로 내 레이아웃으로 들어간다
            nxt = names[0 if d > 0 else -1]
        idx = self.layout_box.findData(nxt)
        if idx < 0:
            return False
        self.layout_box.setCurrentIndex(idx)  # 시그널 → _select_layout 이 통째로 교체
        return True

    def show_preview_frame(self, qimage):
        self._last_frame = qimage          # 결과 미리보기에 실제 카메라 화면 사용
        if not self.isVisible():
            return                         # 촬영 중엔 설정 화면이 숨겨져 있다 — 스케일 낭비 금지
        pm = QPixmap.fromImage(qimage)
        if self.preview.text():            # 실패 안내가 떠 있었다면 원래 모습으로 되돌린다
            self.preview.setText("")
            self.preview.setStyleSheet(
                f"background:#05070b; border:1px solid {LINE}; border-radius:12px;"
                f"color:{MUTED}; font-size:16px;")
        self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.FastTransformation))
        self.cam_status.setText("● 연결됨")
        self.cam_status.setStyleSheet(f"color:{OK_GREEN}; font-size:15px; font-weight:700;")

    def set_camera_list(self, names):
        """names: 카메라 장치 '이름' 목록(ffmpeg dshow)."""
        self._suppress_reconnect = True  # 프로그램적 변경은 자동 재연결 트리거 금지
        cur = self.device_combo.currentData()
        self.device_combo.clear()
        if names:
            for n in names:
                self.device_combo.addItem(n, n)
            if cur in names:
                self.device_combo.setCurrentIndex(names.index(cur))
            self.cam_status.setText(f"● 카메라 {len(names)}개")
            self.cam_status.setStyleSheet(f"color:{OK_GREEN}; font-size:15px; font-weight:700;")
        else:
            self.device_combo.addItem("카메라 없음", "")
            self.cam_status.setText("● 없음")
            self.cam_status.setStyleSheet(f"color:{MUTED}; font-size:15px; font-weight:700;")
        self._suppress_reconnect = False

    def set_preview_failed(self):
        """연결 실패 안내(다시 연결 아이콘으로 재시도 가능)."""
        self.preview.setText("카메라를 찾지 못했어요\n오른쪽 위 ⟳ 로 다시 연결하거나 USB를 확인하세요")
        self.cam_status.setText("● 연결 실패")
        self.cam_status.setStyleSheet(f"color:#FF8A9B; font-size:15px; font-weight:700;")

    def collect(self) -> dict:
        cfg = dict(self.config)
        name = self.device_combo.currentData()
        rw, rh = self._res_map.get(self.res_box.currentText(), (1920, 1080))
        cfg["camera"] = {"backend": self.backend_box.currentText(),
                         "device_name": name or "",
                         "device_index": max(0, self.device_combo.currentIndex()),
                         "width": rw, "height": rh}
        cfg["countdown_sec"] = self.countdown.value()
        cfg["qr_prompt_delay"] = self.qr_delay.value()
        cfg["auto_return_sec"] = self.autoreturn.value()
        cfg["ready_timeout_sec"] = self.ready_timeout.value()
        cfg["abandon_timeout_sec"] = self.abandon_timeout.value()
        cfg["trigger_key"] = self.trigger_btn.key_name or "Space"
        cfg["template_path"] = self.template_edit.text().strip()
        cfg["save_path"] = self.save_edit.text().strip() or "results"
        cfg["jpeg_quality"] = self._q_map.get(self.quality_box.currentText(), 97)
        cfg["flash_enabled"] = self.flash_chk.isChecked()
        cfg["sound_enabled"] = self.sound_chk.isChecked()
        cfg["mirror_preview"] = self.mirror_chk.isChecked()
        cfg["keep_cuts"] = self.keepcuts_chk.isChecked()
        cfg["cloud_share_enabled"] = self.cloud_chk.isChecked()
        cfg["reveal_enabled"] = self.reveal_chk.isChecked()
        cfg["reveal_sec"] = self.reveal_sec.value()
        cfg["share_port"] = self.share_port.value()
        cfg["gif_enabled"] = self.gif_chk.isChecked()
        cfg["gif_format"] = self.gif_format.currentText()
        cfg["gif_width"] = self.gif_width.value()
        cfg["gif_fps"] = self.gif_fps.value()
        cfg["tone"] = self.tone_box.currentText()
        cfg["bg_color"] = self.bg_color.text().strip() or "#FFFFFF"
        cfg["brand_text"] = self.brand_text.text().strip()
        cfg["brand_text_color"] = self.brand_text_color.text().strip() or "#222222"
        cfg["brand_text_pos"] = self._text_pos_map.get(self.brand_text_pos.currentText(), "bottom-center")
        cfg["brand_text_pt"] = self.brand_text_pt.value()
        cfg["brand_text_dx"] = self.brand_text_dx.value()
        cfg["brand_text_dy"] = self.brand_text_dy.value()
        cfg["adjust"] = self._collect_adjust()
        cfg["brand_show_date"] = self.brand_date_chk.isChecked()
        cfg["logo_path"] = self.logo_path.text().strip()
        cfg["logo_scale"] = self.logo_scale.value()
        cfg["logo_pos"] = self._logo_pos_map.get(self.logo_pos.currentText(), "bottom-right")
        cfg["page_bg_color"] = self.page_bg.text().strip() or "#0B0E13"
        cfg["page_text_color"] = self.page_fg.text().strip() or "#EEF1F7"
        cfg["page_logo_path"] = self.page_logo.text().strip()
        cfg["page_title"] = self.page_title.text().strip()
        cfg["guest_wifi"] = {
            "mode": ["off", "current", "hotspot"][self.wifi_mode_box.currentIndex()],
            "ssid": self.wifi_ssid.text().strip(),
            "password": self.wifi_pw.text(),
        }
        cfg["slots"] = self.editor.get_slots()
        cfg["canvas_size"] = [self.editor.canvas_w, self.editor.canvas_h]
        cfg["even_layout"] = self.editor.even
        cfg["user_layouts"] = [dict(u) for u in self.user_layouts]      # 사용자 레이아웃 라이브러리
        # 활성 이름은 **실제로 그 배치를 쓰고 있을 때만** 저장한다(빈 값 = 자유 편집 상태).
        cfg["active_layout"] = getattr(self, "_active_layout", "") or ""
        return cfg

    # ── 레이아웃 라이브러리(예시 + 사용자 자체 템플릿) ──────────────────
    def _builtin_entries(self):
        from core.layouts import LAYOUTS
        return [{"name": name, "builtin": True, "template_path": "",
                 "canvas_size": list(lay["canvas_size"]),
                 "slots": [dict(s) for s in lay["slots"]], "even": False}
                for name, lay in LAYOUTS.items()]

    def _all_entries(self):
        return self._builtin_entries() + self.user_layouts

    def _find_entry(self, name):
        for e in self._all_entries():
            if e["name"] == name:
                return e
        return None

    def _match_entry(self, canvas, slots, template):
        """현재 상태와 일치하는 레이아웃 이름. 없으면 None."""
        key = (list(canvas), [(s.get("x"), s.get("y"), s.get("w"), s.get("h")) for s in slots],
               (template or ""))
        for e in self._all_entries():
            cand = (list(e["canvas_size"]),
                    [(s["x"], s["y"], s["w"], s["h"]) for s in e["slots"]],
                    (e.get("template_path") or ""))
            if cand == key:
                return e["name"]
        return None

    def _reload_layout_combo(self, select=None):
        cur = select or (self.layout_box.currentData() if self.layout_box.count() else None)
        self.layout_box.blockSignals(True)
        self.layout_box.clear()
        for e in self._all_entries():
            label = ("★ " + e["name"]) if not e["builtin"] else e["name"]  # ★=사용자 레이아웃
            self.layout_box.addItem(label, e["name"])
        if cur:
            i = self.layout_box.findData(cur)
            if i >= 0:
                self.layout_box.setCurrentIndex(i)
        self.layout_box.blockSignals(False)
        self._update_layout_buttons()

    def _update_layout_buttons(self):
        e = self._find_entry(self.layout_box.currentData())
        is_user = bool(e and not e["builtin"])
        self.rename_btn.setEnabled(is_user)     # 예시는 이름변경·삭제 불가
        self.del_btn.setEnabled(is_user)

    def _select_layout(self, name):
        """레이아웃 전환 — 템플릿·캔버스·슬롯·균등모드를 '통째로' 교체한다.
        (이렇게 전부 교체해야 다른 레이아웃으로 바꿀 때 자체 이미지 크기가 오염되지 않는다.)"""
        e = self._find_entry(name)
        if not e:
            return
        self._active_layout = name
        tpath = e.get("template_path") or ""
        self.template_edit.setText(tpath)
        self.editor.set_template(tpath or None)
        self.editor.set_canvas_size(*e["canvas_size"])
        self.editor.slots = [dict(s) for s in e["slots"]]
        self.editor.sel = None
        self.even_btn.blockSignals(True)
        self.even_btn.setChecked(bool(e.get("even")))
        self.even_btn.blockSignals(False)
        self.editor.set_even(bool(e.get("even")), normalize=False)
        self._style_even_btn()
        self.editor.update()
        self._update_layout_buttons()
        self._refresh_info()

    def _step_layout(self, d):
        n = self.layout_box.count()
        if n:
            self.layout_box.setCurrentIndex(max(0, min(self.layout_box.currentIndex() + d, n - 1)))

    def _unique_layout_name(self, base):
        base = (base or "레이아웃").strip()
        name = base; k = 2
        while self._find_entry(name):
            name = f"{base} ({k})"; k += 1
        return name

    def _add_template_layout(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "템플릿 이미지 선택", "", "이미지 (*.png *.jpg *.jpeg)")
        if not path:
            return
        from PyQt5.QtGui import QImage
        img = QImage(path)
        if img.isNull():
            return
        nw, nh = img.width(), img.height()
        # 슬롯 = 현재 슬롯을 새 캔버스에 비례 변환(구멍 위치 추정)
        ow, oh = self.editor.canvas_w, self.editor.canvas_h
        slots = [dict(s) for s in self.editor.slots]
        # ① 템플릿의 '사진 자리'(투명 구멍/초록 칠)를 그대로 읽는다 — 손으로 맞출 필요가 없다.
        from core.slot_detect import detect_slots
        found = detect_slots(path, want=len(slots) or 4)
        if found:
            slots = found
            ow = oh = 0                      # 아래 비례 변환 건너뜀(이미 실제 좌표다)
        elif ow and oh and (nw, nh) != (ow, oh):
            # ② 구멍을 못 찾으면 **캔버스 비율에 맞는 예시 배치**를 초기값으로(오너 제공 규격).
            from core.layouts import LAYOUTS
            want_r = nw / nh
            best = min(LAYOUTS.values(),
                       key=lambda L: abs(L["canvas_size"][0] / L["canvas_size"][1] - want_r))
            if abs(best["canvas_size"][0] / best["canvas_size"][1] - want_r) < 0.02:
                k = nw / best["canvas_size"][0]
                slots = [{"x": int(round(s["x"] * k)), "y": int(round(s["y"] * k)),
                          "w": int(round(s["w"] * k)), "h": int(round(s["h"] * k))}
                         for s in best["slots"]]
                ow = oh = 0
        if ow and oh and (nw, nh) != (ow, oh):
            # ⚠️ **칸 크기는 가로·세로를 따로 늘리면 안 된다.** 캔버스 비율이 다른 템플릿을
            #    넣으면 칸이 찌그러진다 — 실측: 1200×1800(칸 518×345=1.50)에서 640×1920 템플릿을
            #    추가했더니 276×368 = 0.75(세로)가 되어 "사진 비율이 계속 달라짐"으로 나타났다.
            #    위치는 비례로 옮기되 **크기는 한 배율(작은 쪽)** 로만 줄인다 → 칸 비율 보존.
            sx, sy = nw / ow, nh / oh
            k = min(sx, sy)
            for s in slots:
                s["w"] = max(1, int(round(s["w"] * k)))
                s["h"] = max(1, int(round(s["h"] * k)))
                s["x"] = max(0, min(int(round(s["x"] * sx)), nw - s["w"]))
                s["y"] = max(0, min(int(round(s["y"] * sy)), nh - s["h"]))
        name = self._unique_layout_name(os.path.splitext(os.path.basename(path))[0])
        self.user_layouts.append({"name": name, "builtin": False, "template_path": path,
                                  "canvas_size": [nw, nh], "slots": slots,
                                  "even": self.editor.even})
        self._reload_layout_combo(select=name)
        self._select_layout(name)

    def _rename_layout(self):
        e = self._find_entry(self.layout_box.currentData())
        if not e or e["builtin"]:
            return
        from PyQt5.QtWidgets import QInputDialog
        new, ok = QInputDialog.getText(self, "레이아웃 이름 변경", "새 이름:", text=e["name"])
        new = (new or "").strip()
        if ok and new and new != e["name"] and not self._find_entry(new):
            e["name"] = new
            self._reload_layout_combo(select=new)
            self._refresh_info()

    def _delete_layout(self):
        name = self.layout_box.currentData()
        e = self._find_entry(name)
        if not e or e["builtin"]:
            return
        self.user_layouts = [u for u in self.user_layouts if u["name"] != name]
        self._reload_layout_combo()
        self._select_layout(self.layout_box.currentData())

    def _style_even_btn(self):
        """균등 배치 ON/OFF 시각 표시 — ON=코발트 강조, OFF=회색."""
        on = self.even_btn.isChecked()
        self.even_btn.setText("  균등 ON" if on else "  균등 OFF")
        self.even_btn.setIcon(icons.icon("layout-grid", "#FFFFFF" if on else MUTED, 17))
        if on:
            self.even_btn.setStyleSheet(
                f"QPushButton{{background:{ACCENT}; color:#FFFFFF; border:1px solid {ACCENT};"
                f"border-radius:8px; padding:6px 12px; font-weight:700;}}")
        else:
            self.even_btn.setStyleSheet(
                f"QPushButton{{background:transparent; color:{MUTED}; border:1px solid {LINE};"
                f"border-radius:8px; padding:6px 12px;}}")

    def _toggle_even(self, on):
        """균등 배치 온/오프. 켜면 즉시 같은 크기·간격으로 정렬하고 격자로 묶는다."""
        self.editor.set_even(on, normalize=True)
        self._style_even_btn()
        self._on_slots_edited()

    def _on_slots_edited(self):
        """드래그·방향키·균등배치로 슬롯이 바뀌면 **지금 편집 중인 레이아웃에만** 반영.

        ⚠️ 활성 레이아웃의 출처는 `self._active_layout` 하나로 통일한다. 예전엔 콤보의
        currentData() 를 읽었는데, 콤보를 거치지 않고 레이아웃을 바꾸는 경로가 있어
        **다른 레이아웃 항목에 편집이 저장되는** 사고가 났다(실측 재현: 2번을 옮겼는데 1번이 바뀜).

        예시(빌트인)를 편집하면 저장할 곳이 없어 전환하는 순간 조용히 사라졌다 →
        **첫 편집에서 사용자 레이아웃 사본으로 승격**해 원본 예시는 보존하고 편집은 살린다.
        """
        name = getattr(self, "_active_layout", None) or self.layout_box.currentData()
        e = self._find_entry(name)
        if e is None:
            self._refresh_info(); return
        if e["builtin"]:
            e = self._promote_builtin(e)
            if e is None:
                self._refresh_info(); return
        e["slots"] = self.editor.get_slots()
        e["canvas_size"] = [self.editor.canvas_w, self.editor.canvas_h]
        e["even"] = self.editor.even
        self._refresh_info()

    def layout_preview_pixmap(self, entry=None):
        """레이아웃 미리보기 그림 — 템플릿 이미지가 있으면 그것, 없으면 칸 배치를 그린다.
        (손님 화면에서도 같은 그림을 쓰므로 여기 하나만 둔다.)"""
        from PyQt5.QtGui import QPixmap, QPainter, QColor
        e = entry if entry is not None else self._find_entry(getattr(self, "_active_layout", None))
        tp = (e or {}).get("template_path") or ""
        if tp:
            pm = QPixmap(tp)
            if not pm.isNull():
                return pm
        cw, ch = (e or {}).get("canvas_size") or [self.editor.canvas_w, self.editor.canvas_h]
        slots = (e or {}).get("slots") or self.editor.get_slots()
        pm = QPixmap(int(cw), int(ch)); pm.fill(QColor("#FFFFFF"))
        pt = QPainter(pm)
        pt.setBrush(QColor("#D8DEE9")); pt.setPen(QColor(ACCENT))
        for s in slots:
            pt.drawRect(int(s["x"]), int(s["y"]), int(s["w"]), int(s["h"]))
        pt.end()
        return pm

    def _promote_builtin(self, entry):
        """예시를 편집하면 사용자 레이아웃 사본을 만들어 그쪽으로 옮긴다(예시 원본은 그대로)."""
        name = self._unique_layout_name(f"{entry['name']} 수정본")
        copy = {"name": name, "builtin": False,
                "template_path": entry.get("template_path") or self.template_edit.text().strip(),
                "canvas_size": [self.editor.canvas_w, self.editor.canvas_h],
                "slots": self.editor.get_slots(), "even": self.editor.even}
        self.user_layouts.append(copy)
        self._active_layout = name
        self._reload_layout_combo(select=name)
        self._update_layout_buttons()
        return copy

    def _detect_slots_now(self):
        """지금 레이아웃의 템플릿에서 사진 자리를 다시 읽어 칸을 맞춘다.

        ⚠️ 못 찾으면 **아무것도 바꾸지 않고** 이유를 알려준다 — 조용히 엉뚱한 칸을 넣으면
        손님 사진이 잘린 채로 나간다.
        """
        from PyQt5.QtWidgets import QMessageBox
        from core.slot_detect import detect_slots
        path = (self.template_edit.text() or "").strip()
        if not path:
            QMessageBox.information(self, "칸 자동 인식",
                                    "이 레이아웃에는 템플릿 이미지가 없습니다.\n"
                                    "‘이미지 추가’로 템플릿을 넣은 뒤 다시 시도하세요.")
            return
        found = detect_slots(path, want=len(self.editor.slots) or 4)
        if not found:
            QMessageBox.information(self, "칸 자동 인식",
                                    "사진 자리를 찾지 못했습니다.\n"
                                    "템플릿의 사진 자리가 투명하게 뚫려 있거나 초록으로 칠해져 있어야 합니다.")
            return
        self.editor.slots = [dict(s) for s in found]
        self.editor.sel = None
        self.editor.update()
        self._on_slots_edited()
        s = found[0]
        QMessageBox.information(self, "칸 자동 인식",
                                f"사진 자리 {len(found)}개를 찾았습니다.\n"
                                f"칸 {s['w']}×{s['h']} (비율 {s['w']/s['h']:.2f})")

    def _export_examples(self):
        from core.layouts import export_all_examples
        from core.platform_utils import open_folder
        out = QFileDialog.getExistingDirectory(self, "예시 템플릿을 저장할 폴더 선택")
        if not out:
            return
        try:
            export_all_examples(out)
            open_folder(out)
        except Exception:
            pass

    def _apply_template(self, path):
        from PyQt5.QtGui import QImage
        img = QImage(path)
        if not img.isNull():
            nw, nh = img.width(), img.height()
            ow, oh = self.editor.canvas_w, self.editor.canvas_h
            # ⚠️ 핵심: 템플릿을 적용하면 캔버스 좌표계가 '템플릿 픽셀 크기'로 바뀐다.
            #    이때 슬롯을 함께 비례 변환하지 않으면, 다른 크기로 만든 템플릿에서 슬롯이
            #    프레임을 벗어나거나(폭 초과) 캔버스 밖으로 나가(아래 컷 소실) 합성이 깨진다.
            #    (실측: 1920×2224 좌표의 슬롯 + 864×1001 템플릿 → 아래 2컷이 캔버스 밖)
            if ow and oh and (nw, nh) != (ow, oh):
                sx, sy = nw / ow, nh / oh
                for sl in self.editor.slots:
                    sl["x"] = int(round(sl["x"] * sx)); sl["y"] = int(round(sl["y"] * sy))
                    sl["w"] = int(round(sl["w"] * sx)); sl["h"] = int(round(sl["h"] * sy))
            self.editor.set_canvas_size(nw, nh)
            self.editor.update()
            self._refresh_info()
        self.editor.set_template(path)

    def _pick_template(self):
        # 자체 템플릿을 고르면 새 '사용자 레이아웃'으로 추가(레이아웃별 이미지 관리)
        self._add_template_layout()

    def _pick_save(self):
        p = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")
        if p:
            self.save_edit.setText(p)

    # ── 브랜딩 라이브 미리보기 ────────────────────────────────────────
    def _fixed_sample_photos(self):
        """'사진 없는 완성본' — 사진 자리는 비운 중립 회색으로 채운다.
        프레임 색·문구·로고만 눈에 들어오게 해서 디자인 확인에 집중되도록."""
        if getattr(self, "_sample_cache", None):
            return self._sample_cache
        import tempfile
        from pathlib import Path as _P
        from PIL import Image
        d = _P(tempfile.mkdtemp(prefix="snapstamp_sample_"))
        p = str(d / "empty.png")
        Image.new("RGB", (640, 360), (226, 229, 234)).save(p)   # 비어있는 사진 자리
        self._sample_cache = [p] * 4
        return self._sample_cache

    def _reset_adjust(self):
        for sl in (self.adj_bright, self.adj_contrast, self.adj_sat, self.adj_sharp):
            sl.setValue(0)

    def _toggle_single_view(self, on: bool):
        """사진 한 장만 크게 ↔ 4컷 전체. 색감·보정은 한 장을 크게 봐야 판단된다."""
        self.single_btn.setText("  4컷 전체 보기" if on else "  사진 1장만 크게")
        self._queue_brand_preview()

    def _collect_adjust(self) -> dict:
        return {"brightness": self.adj_bright.value(), "contrast": self.adj_contrast.value(),
                "saturation": self.adj_sat.value(), "sharpness": self.adj_sharp.value()}

    def _take_test_shot(self):
        """지금 카메라 화면 1장을 찍어 미리보기 4컷에 채운다 — 색감·보정 확인용."""
        import tempfile
        from pathlib import Path as _P
        if self._last_frame is None or self._last_frame.isNull():
            self.brand_preview.setText("카메라가 연결되어 있지 않습니다\n(설정 화면에서 연결 확인)")
            return
        p = str(_P(tempfile.gettempdir()) / "snapstamp_testshot.png")
        self._last_frame.save(p)
        self._test_photo = [p] * 4
        self._render_brand_preview()

    def _clear_test_shot(self):
        self._test_photo = None
        self._render_brand_preview()

    def _preview_photos(self):
        return getattr(self, "_test_photo", None) or self._fixed_sample_photos()

    def _queue_brand_preview(self, *_):
        """연타/타이핑 중 과도한 렌더 방지 — 짧게 모아서 한 번만 그린다."""
        if not hasattr(self, "_brand_timer"):
            from PyQt5.QtCore import QTimer
            self._brand_timer = QTimer(self); self._brand_timer.setSingleShot(True)
            self._brand_timer.timeout.connect(self._render_brand_preview)
        self._brand_timer.start(140)

    def _render_brand_preview(self):
        """현재 브랜딩/색감 값을 축소 캔버스로 빠르게 합성해 우측 패널에 표시."""
        if not hasattr(self, "brand_preview"):
            return
        import tempfile
        from pathlib import Path as _P
        from core.compositor import compose
        # 패널의 '실제' 크기 기준. 패널은 SizePolicy=Ignored 라 내용에 밀리지 않으므로
        # 되먹임(계속 커짐) 없이 안전하고, 잘리지도 않는다.
        pane = getattr(self, "_preview_pane", None)
        if pane is not None and pane.width() > 200 and pane.height() > 200:
            box_w = max(260, pane.width() - 56)     # 좌우 여백
            box_h = max(220, pane.height() - 200)   # 제목·설명·버튼줄·여백
        else:
            box_w, box_h = self._preview_box
        try:
            # ── 사진 1장만 크게 보기 — 색감/보정을 크게 확인 ──
            if getattr(self, "single_btn", None) is not None and self.single_btn.isChecked():
                from PIL import Image
                from core.tone import apply_look
                src = self._preview_photos()[0]
                im = apply_look(Image.open(src).convert("RGB"),
                                self.tone_box.currentText(), self._collect_adjust())
                one = str(_P(tempfile.gettempdir()) / "snapstamp_one_preview.jpg")
                im.save(one, quality=88)
                pm1 = QPixmap(one)
                if not pm1.isNull():
                    s1 = pm1.scaled(box_w, box_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.brand_preview.setPixmap(s1)
                    self.brand_preview.setFixedSize(s1.size())
                    if getattr(self, "_brand_frame", None) is not None:
                        self._brand_frame.setFixedSize(s1.size())
                return
            cw, ch = self.editor.canvas_w, self.editor.canvas_h
            slots = self.editor.get_slots()
            # 내부 렌더는 충분히 크게(가로 900 기준) → 완성본과 같은 비율. 표시할 때만 축소.
            f = min(1.0, 900 / max(1, cw))
            sc = (max(1, int(cw * f)), max(1, int(ch * f)))
            sslots = [{"x": int(s["x"] * f), "y": int(s["y"] * f),
                       "w": max(1, int(s["w"] * f)), "h": max(1, int(s["h"] * f))} for s in slots]
            tpl = self.template_edit.text().strip()
            if tpl and _P(tpl).exists():                # 템플릿도 같은 비율로 축소
                from PIL import Image
                t = Image.open(tpl).convert("RGBA").resize(sc, Image.LANCZOS)
                tpl = str(_P(tempfile.gettempdir()) / "snapstamp_tpl_preview.png"); t.save(tpl)
            else:
                tpl = None
            out = str(_P(tempfile.gettempdir()) / "snapstamp_brand_preview.jpg")
            compose(tpl, sslots, self._preview_photos(), out,
                    canvas_size=None if tpl else sc, quality=85,
                    bg_color=self.bg_color.text().strip() or "#FFFFFF",
                    tone=self.tone_box.currentText(),
                    adjust=self._collect_adjust(),
                    brand={"text": self.brand_text.text().strip(),
                           "text_color": self.brand_text_color.text().strip() or "#222222",
                           "text_pos": self._text_pos_map.get(self.brand_text_pos.currentText(), "bottom-center"),
                           "text_pt": self.brand_text_pt.value(),
                           "text_dx": self.brand_text_dx.value(),
                           "text_dy": self.brand_text_dy.value(),
                           "show_date": self.brand_date_chk.isChecked(),
                           "logo_path": self.logo_path.text().strip(),
                           "logo_scale": self.logo_scale.value(),
                           "logo_pos": self._logo_pos_map.get(self.logo_pos.currentText(), "bottom-right")})
            pm = QPixmap(out)
            if not pm.isNull():
                scaled = pm.scaled(box_w, box_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.brand_preview.setPixmap(scaled)
                # 흰 프레임이 이미지에 딱 맞게 → 남는 흰 여백이 결과물처럼 보이지 않게
                self.brand_preview.setFixedSize(scaled.size())
                if getattr(self, "_brand_frame", None) is not None:
                    self._brand_frame.setFixedSize(scaled.size())  # 여백 없이 딱 맞게
        except Exception as e:  # noqa: BLE001 — 미리보기 실패가 설정을 막지 않게
            self.brand_preview.setText(f"미리보기 실패\n{e}")

    def _swatch_button(self, target: QLineEdit, title: str) -> QPushButton:
        """현재 색을 그대로 보여주는 작은 스와치 버튼(폭 절약 + 색이 한눈에)."""
        b = QPushButton(); b.setFixedSize(46, 44); b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(f"{title} 선택")

        def paint():
            c = target.text().strip() or "#FFFFFF"
            b.setStyleSheet(f"QPushButton{{background:{c}; border:1px solid {HAIR_HI};"
                            f"border-radius:10px;}} QPushButton:hover{{border:2px solid {GOLD};}}")
        target.textChanged.connect(lambda _=None: paint())
        b.clicked.connect(lambda: self._pick_color(target, title))
        paint()
        return b

    def _pick_color(self, target: QLineEdit, title="색 선택"):
        from ui.color_dialog import ColorPickDialog
        picked = ColorPickDialog.pick(target.text().strip() or "#FFFFFF", self, title)
        if picked:
            target.setText(picked)

    def _pick_into(self, target: QLineEdit):
        p, _ = QFileDialog.getOpenFileName(self, "로고 PNG 선택", "", "이미지 (*.png *.jpg *.jpeg)")
        if p:
            target.setText(p)

    def _pick_logo(self):
        p, _ = QFileDialog.getOpenFileName(self, "로고 PNG 선택", "", "이미지 (*.png *.jpg *.jpeg)")
        if p:
            self.logo_path.setText(p)

    def _autofill_dispatch(self):
        # 방식에 맞춰 자동 채우기: 현재 WiFi → 이름만, 모바일 핫스팟 → 이름+비번.
        if self.wifi_mode_box.currentIndex() == 2:
            self._autofill_hotspot()
        else:
            self._autofill_wifi()

    def _on_wifi_mode_changed(self, idx):
        if idx == 2:  # 모바일 핫스팟 선택 시 이름·비번 자동 감지 시도
            self._autofill_hotspot()

    def _autofill_wifi(self):
        """지금 PC가 연결된 WiFi 이름(SSID)을 자동 입력(Windows).

        ⚠️ `netsh wlan show interfaces` 는 **위치 권한이 꺼져 있으면 SSID 를 주지 않는다**
        (Windows 11: "WLAN 정보에 액세스하려면 위치 권한이 필요합니다"). 실측으로 확인했고,
        조용히 실패하면 **지난 장소의 WiFi 이름이 그대로 남아 손님에게 틀린 망을 안내한다.**
        그래서 위치 권한이 필요 없는 연결 프로필 경로를 먼저 쓰고, netsh 는 보조로만 쓴다.
        """
        import subprocess
        ps = ("$ErrorActionPreference='SilentlyContinue';"
              "Get-NetConnectionProfile | Where-Object {"
              "(Get-NetAdapter -InterfaceIndex $_.InterfaceIndex).InterfaceType -eq 71 }"
              " | Select-Object -First 1 -ExpandProperty Name")
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, encoding="utf-8", errors="replace",
                creationflags=0x08000000, timeout=8).stdout or ""
            ssid = out.strip().splitlines()[0].strip() if out.strip() else ""
            if ssid:
                self.wifi_ssid.setText(ssid)
                return
        except Exception:  # noqa: BLE001
            pass
        try:                                   # 보조: 위치 권한이 켜져 있으면 이쪽도 된다
            import re
            out = subprocess.run(["netsh", "wlan", "show", "interfaces"],
                                 capture_output=True, encoding="utf-8", errors="replace",
                                 creationflags=0x08000000, timeout=6).stdout or ""
            m = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.MULTILINE)
            if m:
                self.wifi_ssid.setText(m.group(1).strip())
        except Exception:  # noqa: BLE001
            pass

    def _autofill_hotspot(self):
        """Windows 모바일 핫스팟의 이름(SSID)·비밀번호를 WinRT API로 읽어 자동 입력.
        핫스팟이 구성돼 있어야 하며, 실패하면 조용히 수동 입력에 맡긴다."""
        ps = (
            "$ErrorActionPreference='SilentlyContinue';"
            "[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,"
            "Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]|Out-Null;"
            "$p=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile();"
            "if(-not $p){foreach($x in [Windows.Networking.Connectivity.NetworkInformation]::"
            "GetConnectionProfiles()){if($x){$p=$x;break}}}"
            "$m=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::"
            "CreateFromConnectionProfile($p);"
            "$c=$m.GetCurrentAccessPointConfiguration();"
            "Write-Output ('SSID='+$c.Ssid);Write-Output ('PASS='+$c.Passphrase)"
        )
        try:
            import subprocess
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, encoding="utf-8", errors="replace",
                creationflags=0x08000000, timeout=8).stdout or ""
            ssid = pw = None
            for line in out.splitlines():
                if line.startswith("SSID="):
                    ssid = line[5:].strip()
                elif line.startswith("PASS="):
                    pw = line[5:].strip()
            if ssid:
                self.wifi_ssid.setText(ssid)
            if pw:
                self.wifi_pw.setText(pw)
        except Exception:  # noqa: BLE001
            pass
