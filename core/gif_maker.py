"""움직이는 4컷 만들기 — 촬영 순간의 짧은 클립을 레이아웃대로 합쳐 GIF/MP4로 저장.

사진과 똑같은 배치·배경색·문구·색감/보정을 적용해서 '움직이는 완성본'이 되게 한다.
전부 로컬 처리(계정·업로드 불필요)이며, 해상도를 낮춰 8GB 램에서도 무리 없이 돌아간다.
"""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from core.compositor import cover_fit, _draw_brand
from core.tone import apply_look


def _scaled_slots(slots, f):
    return [{"x": int(s["x"] * f), "y": int(s["y"] * f),
             "w": max(1, int(s["w"] * f)), "h": max(1, int(s["h"] * f))} for s in slots]


def build_frames(clips, slots, canvas_size, bg_color="#FFFFFF", tone=None, adjust=None,
                 brand=None, max_w=720):
    """컷별 클립을 4칸 배치로 합쳐 애니메이션 프레임 목록(RGB)을 만든다."""
    clips = [c for c in clips if c]
    if not clips:
        return []
    cw, ch = canvas_size
    f = min(1.0, max_w / max(1, cw))
    sc = (max(1, int(cw * f)), max(1, int(ch * f)))
    sslots = _scaled_slots(slots, f)
    n = max(len(c) for c in clips)
    # 컷별로 색감/보정을 미리 적용해 두면 프레임마다 반복 계산하지 않는다.
    prepared = []
    for clip in clips:
        prepared.append([apply_look(im.convert("RGB"), tone, adjust) if (tone or adjust)
                         else im.convert("RGB") for im in clip])
    out = []
    for k in range(n):
        canvas = Image.new("RGBA", sc, bg_color or "#FFFFFF")
        for slot, clip in zip(sslots, prepared):
            if not clip:
                continue
            src = clip[min(k, len(clip) - 1)]
            canvas.paste(cover_fit(src.convert("RGBA"), slot["w"], slot["h"]),
                         (slot["x"], slot["y"]))
        _draw_brand(canvas, brand)
        out.append(canvas.convert("RGB"))
    return out


def save_gif(frames, out_path, fps=12) -> Path:
    if not frames:
        raise ValueError("no frames")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    pal[0].save(out, save_all=True, append_images=pal[1:],
                duration=max(20, int(1000 / max(1, fps))), loop=0, optimize=True)
    return out


def save_mp4(frames, out_path, fps=12) -> Path:
    """번들된 ffmpeg로 MP4 저장(인스타는 GIF보다 MP4를 선호)."""
    if not frames:
        raise ValueError("no frames")
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = frames[0].size
    w -= w % 2; h -= h % 2                      # H.264는 짝수 해상도 필요
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-an", "-vcodec", "libx264", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(out)]
    flags = 0x08000000 if __import__("sys").platform.startswith("win") else 0
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags)
    try:
        for fr in frames:
            p.stdin.write(fr.resize((w, h)).tobytes())
    finally:
        try:
            p.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        p.wait(timeout=60)
    return out
