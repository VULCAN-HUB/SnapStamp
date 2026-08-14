from PyQt5.QtCore import QThread, pyqtSignal
from core.gif_maker import build_frames, save_gif, save_mp4


class GifWorker(QThread):
    """움짤 생성은 시간이 걸리므로 백그라운드에서 — 완성 사진은 먼저 보여준다."""
    gif_done = pyqtSignal(str)      # 만들어진 파일 경로
    gif_failed = pyqtSignal(str)

    def __init__(self, clips, slots, canvas_size, out_base, bg_color="#FFFFFF",
                 tone=None, adjust=None, brand=None, fmt="GIF", max_w=720, fps=12,
                 template_path=None):
        super().__init__()
        self.clips = clips
        self.slots = slots
        self.canvas_size = canvas_size
        self.out_base = str(out_base)      # 확장자 없는 경로
        self.bg_color = bg_color
        self.tone = tone
        self.adjust = adjust
        self.brand = brand
        self.fmt = (fmt or "GIF").upper()
        self.max_w = max_w
        self.fps = fps
        self.template_path = template_path

    def run(self):
        try:
            frames = build_frames(self.clips, self.slots, self.canvas_size,
                                  bg_color=self.bg_color, tone=self.tone,
                                  adjust=self.adjust, brand=self.brand, max_w=self.max_w,
                                  template_path=self.template_path)
            if not frames:
                self.gif_failed.emit("클립 없음")
                return
            if self.fmt == "MP4":
                path = save_mp4(frames, self.out_base + ".mp4", fps=self.fps)
            else:
                path = save_gif(frames, self.out_base + ".gif", fps=self.fps)
            self.gif_done.emit(str(path))
        except Exception as e:  # noqa: BLE001
            self.gif_failed.emit(str(e))
