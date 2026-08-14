import sys
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from core.tone import apply_look


def _bundled_font(size: int):
    """번들된 Pretendard(한글 지원)로 텍스트를 그린다. exe(_MEIPASS)·소스 양쪽 대응."""
    base = getattr(sys, "_MEIPASS", None)
    roots = [Path(base) / "assets" / "fonts"] if base else []
    roots.append(Path("assets/fonts"))
    for d in roots:
        for name in ("Pretendard-Bold.ttf", "Pretendard-SemiBold.ttf", "Pretendard-Regular.ttf"):
            p = d / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size=size)
                except Exception:  # noqa: BLE001
                    pass
    for name in ("malgun.ttf", "C:/Windows/Fonts/malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _draw_brand(canvas: Image.Image, brand: dict):
    """운영자가 지정한 문구·날짜·로고를 캔버스에 그린다(템플릿 없이도 브랜딩 가능)."""
    if not brand:
        return
    w, h = canvas.size
    # ⚠️ 최소값을 크게 잡으면 축소 렌더(미리보기)에서 그 값에 걸려 비율이 실제와 달라진다.
    #    바닥값을 아주 낮게 둬서 어떤 크기로 그려도 '완성본과 같은 비율'이 되게 한다.
    margin = max(4, int(min(w, h) * 0.03))
    # ── 문구(행사명 등) + 날짜 ──
    text = (brand.get("text") or "").strip()
    if brand.get("show_date"):
        stamp = datetime.now().strftime("%Y.%m.%d")
        text = f"{text}  ·  {stamp}" if text else stamp
    if text:
        # 글자 크기: 포인트(pt). 캔버스 폭에 맞춰 환산해 어떤 레이아웃에서도 같은 비율로 보인다.
        if brand.get("text_pt"):
            size = max(6, int(float(brand["text_pt"]) * w / 1000.0))
        else:                                     # 구버전 설정 호환(%)
            size = max(6, int(w * (brand.get("text_scale", 4) / 100.0)))
        font = _bundled_font(size)
        d = ImageDraw.Draw(canvas)

        def measure(f):
            try:
                bb = d.textbbox((0, 0), text, font=f)
                return bb[2] - bb[0], bb[3] - bb[1]
            except Exception:  # noqa: BLE001
                return d.textsize(text, font=f)

        tw, th = measure(font)
        # ⚠️ 세로 스트립처럼 좁은 캔버스에서 긴 문구는 폭을 넘어 양옆이 잘린다.
        #    폭에 맞게 글자 크기를 자동으로 줄여 항상 안에 들어오게 한다.
        max_w = max(1, w - 2 * margin)
        if tw > max_w:
            size = max(10, int(size * max_w / tw))
            font = _bundled_font(size)
            tw, th = measure(font)
        # 9방향 위치(가로: 왼쪽/가운데/오른쪽 · 세로: 위/중앙/아래) + 미세 조정(%)
        pos = brand.get("text_pos", "bottom-center")
        if pos == "bottom":
            pos = "bottom-center"
        elif pos == "top":
            pos = "top-center"
        if "left" in pos:
            x = margin
        elif "right" in pos:
            x = max(margin, w - tw - margin)
        else:
            x = max(margin, (w - tw) // 2)
        if "top" in pos:
            y = margin
        elif "bottom" in pos:
            y = h - th - margin - int(th * 0.4)
        else:
            y = (h - th) // 2
        x += int(w * (brand.get("text_dx", 0) or 0) / 100.0)   # 가로 미세 조정
        y += int(h * (brand.get("text_dy", 0) or 0) / 100.0)   # 세로 미세 조정
        x = max(0, min(x, max(0, w - tw)))
        y = max(0, min(y, max(0, h - th)))
        d.text((x, y), text, fill=brand.get("text_color", "#222222"), font=font)
    # ── 로고 워터마크 ──
    logo_path = (brand.get("logo_path") or "").strip()
    if logo_path and Path(logo_path).exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            target_w = max(8, int(w * (brand.get("logo_scale", 15) / 100.0)))
            ratio = target_w / logo.width
            logo = logo.resize((target_w, max(1, int(logo.height * ratio))), Image.LANCZOS)
            pos = brand.get("logo_pos", "bottom-right")
            lx = margin if "left" in pos else w - logo.width - margin
            ly = margin if "top" in pos else h - logo.height - margin
            canvas.alpha_composite(logo, (lx, ly))
        except Exception:  # noqa: BLE001 — 로고 실패가 합성을 막지 않게
            pass


def cover_fit(img: Image.Image, w: int, h: int) -> Image.Image:
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    resized = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return resized.crop((left, top, left + w, top + h))


def compose(template_path, slots, photos, out_path, canvas_size=None, quality=97,
            bg_color="#FFFFFF", tone=None, brand=None, adjust=None) -> Path:
    """4컷 합성.

    bg_color: 템플릿이 없을 때 배경(프레임) 색 — 운영자 커스터마이즈.
    tone:     컷에 적용할 색감 프리셋 이름(core.tone).
    brand:    문구·날짜·로고 워터마크 설정 dict.
    """
    if template_path:
        canvas = Image.open(template_path).convert("RGBA")
    else:
        if canvas_size is None:
            raise ValueError("canvas_size required when template_path is None")
        canvas = Image.new("RGBA", canvas_size, bg_color or "#FFFFFF")

    for slot, photo in zip(slots, photos):
        img = Image.open(photo).convert("RGB")
        if tone or adjust:
            img = apply_look(img, tone, adjust)   # 색감 프리셋 + 밝기/대비/채도/선명도
        fitted = cover_fit(img.convert("RGBA"), slot["w"], slot["h"])
        canvas.paste(fitted, (slot["x"], slot["y"]))

    # 템플릿이 투명 영역(구멍)을 가진 PNG라면 위에 다시 덮어 프레임 유지
    if template_path:
        frame = Image.open(template_path).convert("RGBA")
        canvas.alpha_composite(frame)

    _draw_brand(canvas, brand)   # 문구·날짜·로고는 사진/프레임 위에

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # 최종 JPEG 저장: 품질은 설정값(기본 97). 최고 품질일 때 크로마 서브샘플링 없음(4:4:4).
    # dpi=300 → 100×148mm 캔버스가 실제 엽서 크기로 인쇄된다.
    canvas.convert("RGB").save(out, quality=int(quality),
                               subsampling=0 if quality >= 96 else 2, dpi=(300, 300))
    return out
