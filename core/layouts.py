# -*- coding: utf-8 -*-
"""인생4컷 레이아웃 예시 + 예시 템플릿 PNG 생성.

규격(2026-08-09 오너 확정) — **용지 크기도 컷 비율도 레이아웃마다 다르다.**

| 레이아웃 | 용지 | 컷 비율 | 칸(300DPI) |
|---|---|---|---|
| 세로형(4컷 스트립) | **2×6 인치** (600×1800) | **4:2.5 = 1.600** | 552×345 ×4 + 하단 문구 영역 |
| 아이돌형 | **4×6 인치** (1200×1800) | **6:4 = 1.500** | 521×347 ×4 + 우측 커스텀 이미지 영역 |

**용지는 세로가 길고 사진은 가로가 길다.** 칸 좌표는 오너가 만든 예시 템플릿을 픽셀로 실측해
그대로 옮긴 것이다(위치는 오너가 정한 값 — 임의로 정렬을 고치지 않는다). 캔버스만 정확한
300DPI 크기(640×1920 → 600×1800, 1080×1620 → 1200×1800)로 환산했다.

⚠️ 비율을 말로 받아 적을 때마다 뒤집혔다(3:2 → 4:3 → 3:4 세로 → 16:9). **실물 파일을 픽셀로 잰
값만 안 뒤집혔다.** 그래서 여기 좌표는 계산식이 아니라 실측 표로 박아 둔다.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

DPI = 300


def inch(v: float) -> int:
    """인치 → 300DPI 픽셀."""
    return int(round(v * DPI))


P_2x6 = (inch(2), inch(6))      # (600, 1800)  세로형
P_4x6 = (inch(4), inch(6))      # (1200, 1800) 아이돌형


def _slots(rects):
    return [{"x": x, "y": y, "w": w, "h": h} for (x, y, w, h) in rects]


# 세로형 — 오너 예시 파일(640×1920) **그대로**. 2×6 인치에 인쇄하면 유효 320DPI 라 300 기준을
# 넘으므로 리샘플하지 않는다(줄이면 화질만 버린다). 칸 589×368 @ y=48/438/828/1218, x=26.
_STRIP = {
    "canvas_size": [640, 1920],
    "slots": _slots([(26, 48, 589, 368), (26, 438, 589, 368),
                     (26, 828, 589, 368), (26, 1218, 589, 368)]),
    "guides": [{"x": 26, "y": 1608, "w": 589, "h": 264, "label": "문구 영역"}],
}

# 아이돌형 — 오너 수정본(1200×1800, 이미 정확한 4×6인치 @300DPI) 실측 그대로. 환산 없음.
# 칸 518×345 @ y=52/428/805/1181 (간격 31/32/31), x=57.
_IDOL = {
    "canvas_size": list(P_4x6),
    "slots": _slots([(57, 52, 518, 345), (57, 428, 518, 345),
                     (57, 805, 518, 345), (57, 1181, 518, 345)]),
    "guides": [{"x": 596, "y": 52, "w": 547, "h": 1474, "label": "커스텀 이미지 영역"}],
}

LAYOUTS = {
    "세로형 (4:2.5 · 2x6인치)": _STRIP,
    "아이돌형 (6:4 · 4x6인치)": _IDOL,
}


def make_example_template(name: str, out_path: str) -> Path:
    """레이아웃 예시 템플릿 PNG(300DPI).

    ⚠️ **예시는 촬영용 템플릿이 아니라 '제작 참고용 도면'이다**(오너 확정 2026-08-13).
    사진 자리를 뚫지 않고 **색으로만 구분**한다 — 운영자가 이 규격을 보고 자기 디자인을 만들고,
    **실제 촬영에 쓰는 템플릿은 그 사진 자리를 투명하게 뚫어** 앱에 넣는다(앱은 배경만 받는다).
    """
    lay = LAYOUTS[name]
    w, h = lay["canvas_size"]
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    small = None
    for fname in ("malgun.ttf", "C:/Windows/Fonts/malgun.ttf", "AppleSDGothicNeo.ttc", "arial.ttf"):
        try:
            small = ImageFont.truetype(fname, size=20); break
        except Exception:
            continue
    if small is None:
        small = ImageFont.load_default()

    for g in lay.get("guides", []):          # 문구·이미지 영역은 안내선만(뚫지 않는다)
        x, y, gw, gh = g["x"], g["y"], g["w"], g["h"]
        d.rectangle([x, y, x + gw, y + gh], outline=(150, 158, 170, 255), width=4)
        d.multiline_text((x + gw // 2, y + gh // 2), g.get("label", "이미지 영역"),
                         fill=(150, 158, 170, 255), font=small, anchor="mm", align="center")

    for i, s in enumerate(lay["slots"], 1):
        x, y, sw, sh = s["x"], s["y"], s["w"], s["h"]
        # 사진 자리는 **초록으로 칠해** 눈에 띄게 한다(뚫지 않는다 — 이 파일은 도면이다).
        d.rectangle([x, y, x + sw, y + sh], fill=(40, 190, 110, 255),
                    outline=(20, 120, 70, 255), width=3)
        d.multiline_text((x + sw // 2, y + sh // 2), f"사진 {i}\n{sw}x{sh}",
                         fill=(255, 255, 255, 255), font=small, anchor="mm",
                         align="center", spacing=6)

    inches = f"{w/DPI:.0f}x{h/DPI:.0f}인치"
    note = (f"[{name}] {w}x{h}px · {inches} @ {DPI}DPI · 초록 = 사진 자리 · 회색 = 문구/이미지 영역 "
            f"· 이 파일은 제작 참고용입니다. 실제 템플릿은 초록 자리를 투명하게 뚫어 저장하세요.")
    d.text((8, 8), note, fill=(120, 128, 140, 255), font=small)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, dpi=(DPI, DPI))
    return out


def export_all_examples(out_dir: str) -> list:
    """예시 템플릿 PNG를 폴더에 생성하고 경로 목록 반환."""
    paths = []
    for name in LAYOUTS:
        safe = name.replace(" ", "").replace("·", "-").replace("/", "-").replace(":", "-")
        p = make_example_template(name, str(Path(out_dir) / f"예시_{safe}.png"))
        paths.append(str(p))
    return paths
