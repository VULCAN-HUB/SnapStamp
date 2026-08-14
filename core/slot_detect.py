# -*- coding: utf-8 -*-
"""템플릿 PNG에서 **사진이 들어갈 자리**를 자동으로 찾는다.

인생네컷 템플릿은 사진 자리를 **투명하게 뚫어** 만든다(오너 템플릿도 32~70%가 투명).
그 구멍을 찾으면 운영자가 칸을 손으로 맞출 필요가 없다. 투명이 없으면 **초록 칠**(크로마)도
같은 방식으로 찾는다 — 예시 템플릿이 그 방식이다.

⚠️ 못 찾으면 **아무 값이나 지어내지 않는다**(빈 목록). 부르는 쪽이 예시 배치로 물러선다 —
잘못 찍은 칸은 손님 사진을 조용히 망가뜨린다.

⚠️ 행 단위로 이어 붙이는 방식은 구멍 경계가 1~2px 흔들리면 중간에 끊겨 **높이가 반쪽인 칸**을
만든다(실측: 520×176). 그래서 **연결요소(flood fill)** 로 찾는다. 속도는 긴 변 400px로 줄여서 확보.
"""
from collections import deque
from PIL import Image

MIN_AREA_RATIO = 0.01      # 캔버스의 1% 미만은 구멍이 아니라 글자·장식
FILL_RATIO = 0.80          # 사각형에 가까운 것만(구멍은 네모다)
WORK_W = 400               # 감지용 축소 폭 — 정확도는 충분하고 훨씬 빠르다


def _components(mask, w, h):
    """True 픽셀의 연결 덩어리 → (x0, y0, x1, y1, 픽셀수)."""
    seen = bytearray(w * h)
    out = []
    for sy in range(h):
        base = sy * w
        for sx in range(w):
            if not mask[base + sx] or seen[base + sx]:
                continue
            seen[base + sx] = 1
            q = deque([(sx, sy)])
            x0 = x1 = sx
            y0 = y1 = sy
            n = 0
            while q:
                x, y = q.popleft()
                n += 1
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        i = ny * w + nx
                        if mask[i] and not seen[i]:
                            seen[i] = 1
                            q.append((nx, ny))
            out.append((x0, y0, x1, y1, n))
    return out


def _pick(comps, w, h, want, scale):
    got = []
    for x0, y0, x1, y1, n in comps:
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bw < 6 or bh < 6 or bw * bh < w * h * MIN_AREA_RATIO:
            continue
        if n < bw * bh * FILL_RATIO:          # 속이 꽉 찬 네모만(글자·테두리 제외)
            continue
        got.append({"x": int(round(x0 * scale)), "y": int(round(y0 * scale)),
                    "w": int(round(bw * scale)), "h": int(round(bh * scale))})
    got.sort(key=lambda s: s["w"] * s["h"], reverse=True)
    got = got[:want]
    got.sort(key=lambda s: (s["y"], s["x"]))   # 위→아래, 왼→오른쪽 = 촬영 순서
    return got


def _mask_from(im, w, h, alpha: bool):
    if alpha:
        a = im.convert("RGBA").getchannel("A").resize((w, h), Image.NEAREST)
        return bytearray(1 if v < 16 else 0 for v in a.getdata())
    px = im.convert("RGB").resize((w, h), Image.NEAREST)
    return bytearray(1 if (g > 80 and g > r + 25 and g > b + 25) else 0
                     for r, g, b in px.getdata())


def _refine(im, box, alpha: bool, pad: int):
    """축소본에서 찾은 칸을 **원본 해상도로 다듬는다**(축소 오차만큼 경계가 흔들린다)."""
    ow, oh = im.size
    x0 = max(0, box["x"] - pad); y0 = max(0, box["y"] - pad)
    x1 = min(ow, box["x"] + box["w"] + pad); y1 = min(oh, box["y"] + box["h"] + pad)
    sub = im.crop((x0, y0, x1, y1))
    w, h = sub.size
    if alpha:
        data = sub.convert("RGBA").getchannel("A").getdata()
        hit = [v < 16 for v in data]
    else:
        hit = [(g > 80 and g > r + 25 and g > b + 25) for r, g, b in sub.convert("RGB").getdata()]
    cols = [x for x in range(w) if sum(hit[y * w + x] for y in range(0, h, 4)) > (h // 4) * 0.6]
    rows = [y for y in range(h) if sum(hit[y * w + x] for x in range(0, w, 4)) > (w // 4) * 0.6]
    if not cols or not rows:
        return box
    return {"x": x0 + cols[0], "y": y0 + rows[0],
            "w": cols[-1] - cols[0] + 1, "h": rows[-1] - rows[0] + 1}


def _harmonize(slots):
    """칸 크기를 **중앙값으로 통일**한다(중심은 유지).

    인생네컷 템플릿의 칸은 규격이 같다. 그런데 구멍 옆 반투명 그림자·둥근 모서리 때문에
    한 칸만 몇 px 다르게 잡히는 일이 있다(실측: 1.499 셋 + 1.646 하나). 그대로 두면
    그 컷만 다른 비율로 잘려 "사진 비율이 계속 달라짐"으로 보인다.
    크기가 서로 15% 넘게 다르면(=진짜 다른 디자인) 손대지 않는다.
    """
    if len(slots) < 2:
        return slots
    ws = sorted(s["w"] for s in slots); hs = sorted(s["h"] for s in slots)
    mw = ws[len(ws) // 2]; mh = hs[len(hs) // 2]
    if ws[-1] > ws[0] * 1.15 or hs[-1] > hs[0] * 1.15:
        return slots                     # 의도적으로 크기가 다른 배치 — 그대로 존중
    out = []
    for s in slots:
        cx = s["x"] + s["w"] / 2
        cy = s["y"] + s["h"] / 2
        out.append({"x": int(round(cx - mw / 2)), "y": int(round(cy - mh / 2)),
                    "w": mw, "h": mh})
    return out


def detect_slots(path: str, want: int = 4):
    """템플릿에서 사진 자리 목록(원본 좌표). 못 찾으면 빈 목록."""
    try:
        im = Image.open(path)
    except Exception:  # noqa: BLE001
        return []
    ow, oh = im.size
    if ow <= 0 or oh <= 0:
        return []
    sw = min(WORK_W, ow)
    sh = max(1, int(round(oh * sw / ow)))
    scale = ow / sw
    has_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
    for use_alpha in ((True, False) if has_alpha else (False,)):
        mask = _mask_from(im, sw, sh, use_alpha)
        got = _pick(_components(mask, sw, sh), sw, sh, want, scale)
        if len(got) == want:
            pad = int(scale) + 2
            return _harmonize([_refine(im, b, use_alpha, pad) for b in got])
    return []
