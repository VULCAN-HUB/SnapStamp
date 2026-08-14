# -*- coding: utf-8 -*-
"""촬영·라이브뷰 크롭 비율 = **현재 레이아웃의 사진 칸(슬롯) 비율**.

핵심: 슬롯 비율과 촬영 비율이 다르면 합성 때 `cover_fit`이 넘치는 쪽을 크게 잘라낸다
(상하 또는 좌우가 뭉텅 잘림 = 손님이 본 화면과 결과가 다름). 그래서 고정값을 쓰지 않고
**활성 레이아웃 슬롯에서 비율을 읽어** 촬영·라이브뷰를 같은 비율로 가운데 크롭한다.
→ 손님이 보는 모습 = 받는 사진(WYSIWYG), 잘림 없음.

레이아웃마다 칸 비율이 다르다(4:3 / 1:1 / 16:9 / 3:2). 그 값을 그대로 따른다.
"""
from PIL import Image

DEFAULT_RATIO = 4 / 3          # 슬롯을 못 읽을 때만 쓰는 기본값(가장 흔한 인생네컷 칸)


def slots_ratio(slots, default=DEFAULT_RATIO) -> float:
    """슬롯 목록에서 가로/세로 비율을 얻는다. 칸마다 다르면 첫 칸 기준."""
    try:
        for s in slots or []:
            w, h = float(s.get("w", 0)), float(s.get("h", 0))
            if w > 0 and h > 0:
                return w / h
    except Exception:  # noqa: BLE001
        pass
    return default


def crop_to_ratio(img: "Image.Image", ratio: float = DEFAULT_RATIO) -> "Image.Image":
    """이미지를 가로/세로 = ratio 로 가운데 크롭. 넘치는 쪽만 잘라낸다."""
    w, h = img.size
    if w <= 0 or h <= 0 or not ratio or ratio <= 0:
        return img
    cur = w / h
    if abs(cur - ratio) < 1e-3:
        return img
    if cur > ratio:                # 너무 넓음 → 좌우를 잘라 폭을 줄인다
        nw = max(1, int(round(h * ratio)))
        x = (w - nw) // 2
        return img.crop((x, 0, x + nw, h))
    nh = max(1, int(round(w / ratio)))   # 너무 높음 → 위아래를 잘라 높이를 줄인다
    y = (h - nh) // 2
    return img.crop((0, y, w, y + nh))


def crop_file_to_ratio(path: str, ratio: float = DEFAULT_RATIO) -> None:
    """저장된 촬영본을 제자리에서 ratio로 크롭해 다시 저장한다."""
    try:
        with Image.open(path) as im:
            src = im.convert("RGB")
            out = crop_to_ratio(src, ratio)
            if out.size == src.size:
                return                       # 이미 비율이 맞으면 재저장 안 함
        out.save(path, quality=97, subsampling=0)
    except Exception:  # noqa: BLE001 — 크롭 실패가 촬영 흐름을 막지 않게
        pass
