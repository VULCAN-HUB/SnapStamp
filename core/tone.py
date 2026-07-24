"""색감(톤) 프리셋 — 필름 룩 컬러 그레이딩.

AI 아님. 채널별 256단계 LUT + 채도/대비 조정만 사용하므로 어떤 PC에서도 즉시 동작한다.
같은 함수를 라이브 미리보기와 최종 합성 양쪽에 써서 보이는 대로 나오게(WYSIWYG) 한다.
"""
from PIL import Image, ImageEnhance

NONE = "원본"

# 이름 → (R커브, G커브, B커브, 채도배율, 대비배율, 흑백여부)
# 커브는 (입력0~255 → 출력) 제어점. 사이는 선형 보간.
_PRESETS = {
    NONE: None,
    "따뜻하게": dict(r=[(0, 8), (128, 140), (255, 255)], g=[(0, 4), (128, 130), (255, 252)],
                  b=[(0, 0), (128, 118), (255, 242)], sat=1.05, con=1.02),
    "차갑게": dict(r=[(0, 0), (128, 118), (255, 244)], g=[(0, 2), (128, 128), (255, 250)],
                 b=[(0, 10), (128, 142), (255, 255)], sat=1.02, con=1.03),
    "필름": dict(r=[(0, 18), (60, 74), (128, 138), (200, 210), (255, 248)],
               g=[(0, 16), (60, 70), (128, 132), (200, 205), (255, 245)],
               b=[(0, 26), (60, 76), (128, 126), (200, 194), (255, 235)], sat=0.94, con=1.06),
    "비비드": dict(r=[(0, 0), (128, 132), (255, 255)], g=[(0, 0), (128, 132), (255, 255)],
                b=[(0, 0), (128, 130), (255, 255)], sat=1.35, con=1.12),
    "흑백": dict(r=None, g=None, b=None, sat=1.0, con=1.06, mono=True),
}

PRESET_NAMES = list(_PRESETS.keys())


def _curve(points):
    """제어점 목록 → 256 항목 LUT(선형 보간)."""
    if not points:
        return list(range(256))
    lut = []
    for i in range(256):
        # i 를 감싸는 두 제어점 찾기
        lo = points[0]
        hi = points[-1]
        for a, b in zip(points, points[1:]):
            if a[0] <= i <= b[0]:
                lo, hi = a, b
                break
        if hi[0] == lo[0]:
            v = hi[1]
        else:
            t = (i - lo[0]) / (hi[0] - lo[0])
            v = lo[1] + (hi[1] - lo[1]) * t
        lut.append(max(0, min(255, int(round(v)))))
    return lut


_CACHE = {}


def _lut_for(name):
    if name in _CACHE:
        return _CACHE[name]
    p = _PRESETS.get(name)
    if not p:
        _CACHE[name] = None
        return None
    built = dict(p)
    if not p.get("mono"):
        built["lut"] = _curve(p["r"]) + _curve(p["g"]) + _curve(p["b"])
    _CACHE[name] = built
    return built


def apply_adjust(img: "Image.Image", adj: dict) -> "Image.Image":
    """촬영 전 보정 — 밝기·대비·채도·선명도. 값은 -100~+100(선명도는 0~100).
    0이면 아무 것도 하지 않으므로 기본 상태에선 비용이 없다."""
    if not adj:
        return img
    out = img
    b = int(adj.get("brightness", 0) or 0)
    c = int(adj.get("contrast", 0) or 0)
    s = int(adj.get("saturation", 0) or 0)
    sh = int(adj.get("sharpness", 0) or 0)
    if b:
        out = ImageEnhance.Brightness(out).enhance(1.0 + b / 100.0)
    if c:
        out = ImageEnhance.Contrast(out).enhance(1.0 + c / 100.0)
    if s:
        out = ImageEnhance.Color(out).enhance(1.0 + s / 100.0)
    if sh:
        out = ImageEnhance.Sharpness(out).enhance(1.0 + sh / 50.0)
    return out


def apply_look(img: "Image.Image", tone_name: str = None, adj: dict = None) -> "Image.Image":
    """색감 프리셋 + 수치 보정을 한 번에(미리보기·최종 합성이 같은 결과가 되도록)."""
    out = apply_tone(img, tone_name) if tone_name else img
    return apply_adjust(out, adj)


def apply_tone(img: "Image.Image", name: str) -> "Image.Image":
    """PIL 이미지에 톤 프리셋 적용. 알 수 없는 이름이나 '원본'이면 그대로 반환."""
    p = _lut_for(name)
    if not p:
        return img
    out = img.convert("RGB")
    if p.get("mono"):
        out = out.convert("L").convert("RGB")
    else:
        out = out.point(p["lut"])
    if p.get("sat", 1.0) != 1.0:
        out = ImageEnhance.Color(out).enhance(p["sat"])
    if p.get("con", 1.0) != 1.0:
        out = ImageEnhance.Contrast(out).enhance(p["con"])
    return out
