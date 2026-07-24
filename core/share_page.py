"""손님이 QR로 접속하는 '사진 받기' 페이지 — 운영자 브랜딩이 적용된 HTML.

파일을 따로 만들지 않고 로컬 서버가 요청 시 즉석에서 생성한다(저장 폴더는 계속 깔끔).
사진과 움짤을 한 페이지에서 모두 받을 수 있고, 움짤이 아직이면 '준비 중'을 보여준 뒤
자동으로 새로고침한다.
"""
import base64
import html
from pathlib import Path

_LOGO_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".gif": "image/gif", ".webp": "image/webp"}


def _logo_data_uri(path: str) -> str:
    """로고를 페이지에 직접 심는다(추가 파일·요청 없이 표시)."""
    try:
        p = Path(path)
        if not p.exists() or p.stat().st_size > 2_000_000:
            return ""
        mime = _LOGO_MIME.get(p.suffix.lower(), "image/png")
        return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"
    except Exception:  # noqa: BLE001
        return ""


def render_page(base: str, photo_name: str, motion_name: str = "",
                expect_motion: bool = False, cfg: dict = None) -> str:
    cfg = cfg or {}
    bg = cfg.get("page_bg_color") or "#0B0E13"
    fg = cfg.get("page_text_color") or "#EEF1F7"
    title = html.escape(cfg.get("page_title") or "사진이 준비되었어요")
    logo = _logo_data_uri(cfg.get("page_logo_path") or "")
    muted = "rgba(255,255,255,0.55)" if _is_dark(bg) else "rgba(0,0,0,0.5)"
    card = "rgba(255,255,255,0.07)" if _is_dark(bg) else "rgba(0,0,0,0.05)"
    line = "rgba(255,255,255,0.14)" if _is_dark(bg) else "rgba(0,0,0,0.12)"

    logo_html = (f'<img class="logo" src="{logo}" alt="">' if logo else "")
    photo_html = f"""
    <section class="card">
      <img class="shot" src="/{html.escape(photo_name)}" alt="사진">
      <a class="btn" href="/{html.escape(photo_name)}" download>사진 저장하기</a>
    </section>"""

    if motion_name:
        is_mp4 = motion_name.lower().endswith(".mp4")
        media = (f'<video class="shot" src="/{html.escape(motion_name)}" autoplay loop muted playsinline></video>'
                 if is_mp4 else f'<img class="shot" src="/{html.escape(motion_name)}" alt="움짤">')
        motion_html = f"""
    <section class="card">
      <div class="tag">움직이는 4컷</div>
      {media}
      <a class="btn ghost" href="/{html.escape(motion_name)}" download>움짤 저장하기</a>
    </section>"""
        refresh = ""
    elif expect_motion:
        motion_html = """
    <section class="card waiting">
      <div class="tag">움직이는 4컷</div>
      <div class="spin"></div>
      <p class="wait">움짤을 만들고 있어요… 잠시만요</p>
    </section>"""
        refresh = "<script>setTimeout(function(){location.reload();},4000);</script>"
    else:
        motion_html = ""
        refresh = ""

    return f"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title}</title>
<style>
 *{{box-sizing:border-box}}
 body{{margin:0;padding:22px 16px 40px;background:{bg};color:{fg};
   font-family:-apple-system,BlinkMacSystemFont,'Malgun Gothic','Apple SD Gothic Neo',sans-serif;
   display:flex;flex-direction:column;align-items:center;gap:18px}}
 header{{display:flex;flex-direction:column;align-items:center;gap:10px;text-align:center}}
 .logo{{max-width:180px;max-height:70px;object-fit:contain}}
 h1{{margin:0;font-size:22px;font-weight:800;letter-spacing:-.2px}}
 .sub{{margin:0;color:{muted};font-size:14px}}
 .card{{width:100%;max-width:520px;background:{card};border:1px solid {line};
   border-radius:18px;padding:14px;display:flex;flex-direction:column;align-items:center;gap:12px}}
 .shot{{width:100%;height:auto;border-radius:10px;display:block}}
 .tag{{align-self:flex-start;font-size:12px;font-weight:700;letter-spacing:1.5px;
   color:{muted};text-transform:uppercase}}
 .btn{{display:block;width:100%;text-align:center;padding:15px 18px;border-radius:12px;
   background:#4C7DFF;color:#fff;text-decoration:none;font-size:17px;font-weight:700}}
 .btn.ghost{{background:transparent;border:1px solid {line};color:{fg}}}
 .waiting{{padding:34px 14px}}
 .wait{{margin:0;color:{muted};font-size:15px}}
 .spin{{width:30px;height:30px;border-radius:50%;border:3px solid {line};
   border-top-color:#4C7DFF;animation:sp 1s linear infinite}}
 @keyframes sp{{to{{transform:rotate(360deg)}}}}
 footer{{color:{muted};font-size:13px;text-align:center;line-height:1.6}}
</style></head><body>
<header>{logo_html}<h1>{title}</h1><p class="sub">아래에서 저장하세요</p></header>
{photo_html}{motion_html}
<footer>부스 운영 중에만 받을 수 있어요 · 지금 저장해 주세요</footer>
{refresh}
</body></html>"""


def _is_dark(hex_color: str) -> bool:
    try:
        c = hex_color.lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return (r * 299 + g * 587 + b * 114) / 1000 < 128
    except Exception:  # noqa: BLE001
        return True
