# -*- coding: utf-8 -*-
"""안내서용 스크린샷 후처리 — 개인정보 마스킹 + 크롭.

캡처 원본(shots/_raw/)은 촬영 장소가 그대로 찍히므로 배포 문서에 쓸 수 없다.
이 스크립트가 ① 카메라 영상 영역을 흐리게 처리하고 ② 브라우저 크롬(프로필 아이콘 등)과
작업표시줄을 잘라내어 shots/ 에 배포용 이미지를 만든다.

⚠️ PII 규칙: 실제 촬영 장소·브라우저 계정 표시·실제 Wi-Fi 이름/비밀번호가
   안내서에 들어가면 안 된다. 원본은 로컬에만 두고 배포본은 항상 이 스크립트를 거친다.

사용: python docs/manual/prepare_shots.py
"""
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw

BASE = Path(__file__).parent
RAW = BASE / "shots" / "_raw"
OUT = BASE / "shots"

# 파일별 처리 규칙
#   crop : 먼저 잘라낼 영역 (원본 좌표)
#   blur : 흐리게 처리할 사각형들 (좌, 상, 우, 하) — ⚠️ crop 이 있으면 '크롭된 뒤' 좌표
#
# ⚠️ 순서 주의: crop → blur 순으로 적용한다. 반대로 하면 좌표가 어긋나
#    가려야 할 곳(아래쪽 사진)이 노출되고 남겨야 할 곳(제목)이 뭉개진다. 실제로 겪은 실수다.
RULES = {
    "01_setup.png":     {"blur": [(47, 143, 470, 386)]},
    "02_attract.png":   {"blur": [(1174, 370, 1863, 765)]},
    "03_ready.png":     {"blur": [(168, 96, 1752, 988)]},
    # 카운트다운은 숫자·링이 설명의 핵심이라 블러로 뭉개면 그림 의미가 없다.
    # 배경(카메라 영상)은 가리되, 흰 숫자와 코발트 링 픽셀만 원본에서 되살린다.
    "04_countdown.png": {"blur": [(168, 96, 1752, 988)],
                         "restore": {"box": (700, 280, 1220, 800),
                                     "colors": [(255, 255, 255), (76, 125, 255)],
                                     "tol": 70}},
    "05_result.png":    {"blur": [(610, 106, 988, 962)]},
    # 브라우저 크롬(프로필 아이콘)과 작업표시줄을 잘라낸 뒤, 사진 영역만 아래 끝까지 가린다.
    # 제목("사진이 준비되었어요")은 남겨야 하므로 블러 상단을 사진 시작점 아래로 잡는다.
    "06_guestpage.png": {"crop": (0, 110, 1910, 1020), "blur": [(645, 140, 1260, 910)]},
}

BLUR_RADIUS = 18


def process(name, rule):
    src = RAW / name
    if not src.exists():
        print(f"  건너뜀(원본 없음): {name}")
        return False
    im = Image.open(src).convert("RGB")

    # 1) 먼저 자른다 — blur 좌표는 잘린 뒤 기준이다.
    if "crop" in rule:
        im = im.crop(rule["crop"])

    # 2) 그 다음 가린다. 지정 영역이 이미지 밖으로 나가면 이미지 경계로 잘라 안전하게 처리.
    W, H = im.size
    for box in rule.get("blur", []):
        l, t, r, b = box
        box = (max(0, l), max(0, t), min(W, r), min(H, b))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        region = im.crop(box).filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
        im.paste(region, box)

    # 3) UI 요소 되살리기 — 지정 색과 가까운 픽셀만 원본에서 복원한다.
    #    (카운트다운 숫자/링처럼 설명에 꼭 필요한 요소가 블러에 먹히는 것을 막는다)
    rs = rule.get("restore")
    if rs:
        orig = Image.open(src).convert("RGB")
        if "crop" in rule:
            orig = orig.crop(rule["crop"])
        box = rs["box"]
        cut_o, cut_b = orig.crop(box), im.crop(box)
        px_o, px_b = cut_o.load(), cut_b.load()
        tol = rs.get("tol", 60)
        bw, bh = cut_o.size
        for y in range(bh):
            for x in range(bw):
                r, g, b = px_o[x, y]
                for cr, cg, cb in rs["colors"]:
                    if abs(r - cr) <= tol and abs(g - cg) <= tol and abs(b - cb) <= tol:
                        px_b[x, y] = (r, g, b)
                        break
        im.paste(cut_b, box)

    im.save(OUT / name)
    print(f"  완료: {name}  {im.size}")
    return True


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not RAW.exists():
        print(f"원본 폴더가 없습니다: {RAW}")
        return
    print("스크린샷 후처리(개인정보 마스킹)")
    n = sum(process(k, v) for k, v in RULES.items())
    print(f"\n{n}개 처리 완료 → {OUT}")


if __name__ == "__main__":
    main()
