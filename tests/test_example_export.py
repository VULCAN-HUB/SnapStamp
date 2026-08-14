"""내보낸 예시는 **제작 참고용 도면**이다 — 촬영용 템플릿이 아니다(오너 확정 2026-08-13).

- 사진 자리는 **색(초록)으로만 구분**하고 뚫지 않는다. 운영자가 이 규격을 보고 자기 디자인을 만든다.
- 실제 촬영에 쓰는 템플릿은 그 자리를 **투명하게 뚫어** 앱에 넣는다(앱은 배경만 받는다).
- 인쇄 크기가 틀어지지 않게 300DPI 메타는 반드시 들어간다.
"""
from PIL import Image
from core.layouts import LAYOUTS, export_all_examples


def test_examples_are_reference_sheets_not_cut_out_templates(tmp_path):
    paths = export_all_examples(str(tmp_path))
    assert len(paths) == len(LAYOUTS)

    for name, path in zip(LAYOUTS, paths):
        with Image.open(path) as im:
            assert im.size == tuple(LAYOUTS[name]["canvas_size"])
            rgba = im.convert("RGBA")
            holes = sum(1 for v in rgba.getchannel("A").getdata() if v < 16)
            assert holes == 0, f"{name}: 예시는 뚫지 않는다(참고용 도면)"

            px = rgba.load()
            s = LAYOUTS[name]["slots"][0]
            r, g, b, _ = px[s["x"] + s["w"] // 2, s["y"] + 6]      # 칸 안쪽(글자 없는 지점)
            assert g > 120 and g > r + 40 and g > b + 40,                 f"{name}: 사진 자리가 색으로 구분되지 않는다 (rgb={r},{g},{b})"


def test_dpi_metadata_is_kept(tmp_path):
    for path in export_all_examples(str(tmp_path)):
        with Image.open(path) as im:
            dpi = im.info.get("dpi")
            assert dpi and round(dpi[0]) == 300 and round(dpi[1]) == 300, f"{path}: dpi={dpi}"
