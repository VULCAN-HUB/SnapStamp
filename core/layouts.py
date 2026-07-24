"""인생4컷 레이아웃 프리셋 + 예시 템플릿 PNG 생성.

각 레이아웃은 캔버스 크기와 4개 슬롯 위치를 정의한다. 사용자가 이 예시 PNG를
기준으로 디자인(프레임/브랜딩)을 만들고, 슬롯 영역을 투명하게 뚫으면 그 자리에
사진이 들어간다. 앱에서 레이아웃을 고르면 캔버스·슬롯이 이 값으로 설정된다.

사진 컷은 항상 가로형(16:9, 카메라 원본 그대로, 크롭 없음). 배치(가로/세로)만 다름.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

M = 40    # 바깥 여백
G = 40    # 슬롯 간격
LAND = (1920, 1080)   # 가로 컷(16:9)
STRIP = (1600, 900)   # 스트립용 가로 컷(16:9, 조금 작게)


def _grid(cols, rows, cw, ch):
    slots = []
    for r in range(rows):
        for c in range(cols):
            slots.append({"x": M + c * (cw + G), "y": M + r * (ch + G), "w": cw, "h": ch})
    canvas = [M * 2 + cols * cw + (cols - 1) * G, M * 2 + rows * ch + (rows - 1) * G]
    return canvas, slots


def _make(cols, rows, cut):
    cw, ch = cut
    canvas, slots = _grid(cols, rows, cw, ch)
    return {"canvas_size": canvas, "slots": slots}


def _strip_bottom_text(cut, bottom_h=360):
    """세로 4컷 스트립 + 하단 문구 영역(ZEROBASEONE 스타일)."""
    cw, ch = cut
    slots = [{"x": M, "y": M + i * (ch + G), "w": cw, "h": ch} for i in range(4)]
    top = M + 4 * ch + 3 * G
    canvas = [M * 2 + cw, top + G + bottom_h + M]
    guides = [{"x": M, "y": top + G, "w": cw, "h": bottom_h, "label": "문구 영역"}]
    return {"canvas_size": canvas, "slots": slots, "guides": guides}


def _idol_lr():
    """중심선 기준 좌=사진 4컷(세로 배치·가로형 사진), 우=이미지 영역. 좌우 균형(여백 최소)."""
    pw, ph = 900, 506           # 좌측 컷(가로형 16:9)
    col_h = 4 * ph + 3 * G      # 사진 열 높이
    right_x = M + pw + G
    right_w = pw                # 우측 이미지 영역 = 좌측 폭과 동일(좌우 균형)
    canvas = [right_x + right_w + M, M + col_h + M]
    slots = [{"x": M, "y": M + i * (ph + G), "w": pw, "h": ph} for i in range(4)]
    guides = [{"x": right_x, "y": M, "w": right_w, "h": col_h, "label": "이미지 영역"}]
    return {"canvas_size": canvas, "slots": slots, "guides": guides}


def _grid_bottom_text(cols, rows, cut, bottom_h=300):
    base = _make(cols, rows, cut)
    w, h = base["canvas_size"]
    guides = [{"x": M, "y": h + G, "w": w - 2 * M, "h": bottom_h, "label": "문구 영역"}]
    base["canvas_size"] = [w, h + G + bottom_h + M]
    base["guides"] = guides
    return base


def _grid_top_text(cols, rows, cut, top_h=300):
    """상단 문구/로고 밴드 + 하단 컷 그리드."""
    base = _make(cols, rows, cut)
    w, h = base["canvas_size"]
    for s in base["slots"]:
        s["y"] += top_h + G
    base["canvas_size"] = [w, h + top_h + G]
    base["guides"] = [{"x": M, "y": M, "w": w - 2 * M, "h": top_h, "label": "로고/문구 영역"}]
    return base


def _idol_top(cut=(900, 506), band_h=380):
    """상단 이미지/로고 밴드 + 하단 2x2 컷(아이돌 포토카드 스타일)."""
    cw, ch = cut
    grid_w = 2 * cw + G
    top = M + band_h + G
    slots = []
    for r in range(2):
        for c in range(2):
            slots.append({"x": M + c * (cw + G), "y": top + r * (ch + G), "w": cw, "h": ch})
    canvas = [M * 2 + grid_w, top + 2 * ch + G + M]
    guides = [{"x": M, "y": M, "w": grid_w, "h": band_h, "label": "이미지/로고 영역"}]
    return {"canvas_size": canvas, "slots": slots, "guides": guides}


# 레이아웃 (표시이름 → 정의). 사진은 모두 가로형(16:9) 4컷, 배치만 다름.
LAYOUTS = {
    "가로 2x2": _make(2, 2, LAND),
    "가로 1x4": _make(4, 1, LAND),                 # 가로로 4컷 나열
    "세로 4x1": _make(1, 4, LAND),                 # 세로로 4컷 쌓기(인생4컷 스트립)
    "세로 4x1 (클래식·좁게)": _make(1, 4, (1280, 720)),  # 좁은 클래식 스트립
    "세로 4x1 (하단문구)": _strip_bottom_text(LAND),
    "세로 4x1 (상단문구)": _grid_top_text(1, 4, LAND, top_h=360),
    "가로 2x2 (하단문구)": _grid_bottom_text(2, 2, LAND),
    "가로 2x2 (상단문구)": _grid_top_text(2, 2, LAND),
    "가로 1x4 (하단문구)": _grid_bottom_text(4, 1, LAND, bottom_h=260),
    "아이돌 (좌4컷+우이미지)": _idol_lr(),
    "아이돌 (상이미지+하2x2)": _idol_top(),
}


def make_example_template(name: str, out_path: str) -> Path:
    """레이아웃 예시 가이드 PNG 생성. 흰 배경 + 슬롯 영역(연회색)과 번호 표시.
    사용자는 이 위에 디자인하고, 실제 템플릿에선 슬롯 영역을 투명하게 뚫으면 된다."""
    lay = LAYOUTS[name]
    w, h = lay["canvas_size"]
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    size = max(48, min(w, h) // 14)
    font = None
    for fname in ("malgun.ttf", "C:/Windows/Fonts/malgun.ttf", "AppleSDGothicNeo.ttc", "arial.ttf"):
        try:
            font = ImageFont.truetype(fname, size=size); break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    # 사진 슬롯(파란색 — 여기에 촬영 사진이 들어감. 실제 템플릿에선 투명하게 뚫기)
    for i, s in enumerate(lay["slots"], 1):
        x, y, sw, sh = s["x"], s["y"], s["w"], s["h"]
        d.rectangle([x, y, x + sw, y + sh], fill=(224, 228, 234, 255),
                    outline=(61, 107, 255, 255), width=6)
        d.multiline_text((x + sw // 2, y + sh // 2), f"사진 {i}\n{sw}x{sh}",
                         fill=(90, 100, 120, 255), font=font, anchor="mm",
                         align="center", spacing=10)
    # 디자인/문구 가이드 영역(회색 점선 — 사용자가 텍스트/그래픽을 넣는 자리)
    for g in lay.get("guides", []):
        x, y, gw, gh = g["x"], g["y"], g["w"], g["h"]
        d.rectangle([x, y, x + gw, y + gh], outline=(150, 158, 170, 255), width=4)
        d.multiline_text((x + gw // 2, y + gh // 2), g.get("label", "문구 영역"),
                         fill=(150, 158, 170, 255), font=font, anchor="mm",
                         align="center", spacing=10)
    small = None
    for fname in ("malgun.ttf", "C:/Windows/Fonts/malgun.ttf", "arial.ttf"):
        try:
            small = ImageFont.truetype(fname, size=26); break
        except Exception:
            continue
    note = f"[{name}] {w}x{h}  ·  파랑=사진자리(투명화) · 회색=문구/디자인 자리"
    d.text((6, 6), note, fill=(120, 128, 140, 255), font=small or font)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def export_all_examples(out_dir: str) -> list[str]:
    """4종 예시 템플릿 PNG를 폴더에 생성하고 경로 목록 반환."""
    paths = []
    for name in LAYOUTS:
        p = make_example_template(name, str(Path(out_dir) / f"예시_{name.replace(' ', '')}.png"))
        paths.append(str(p))
    return paths
