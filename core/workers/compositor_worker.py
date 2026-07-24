from PyQt5.QtCore import QThread, pyqtSignal
from core.compositor import compose


class CompositorWorker(QThread):
    composite_done = pyqtSignal(str)
    composite_failed = pyqtSignal(str)

    def __init__(self, template_path, slots, photos, out_path, canvas_size=None, quality=97,
                 bg_color="#FFFFFF", tone=None, brand=None, adjust=None):
        super().__init__()
        self.template_path = template_path
        self.slots = slots
        self.photos = photos
        self.out_path = out_path
        self.canvas_size = canvas_size
        self.quality = quality
        self.bg_color = bg_color
        self.tone = tone
        self.brand = brand
        self.adjust = adjust

    def run(self):
        try:
            result = compose(self.template_path, self.slots, self.photos,
                             self.out_path, canvas_size=self.canvas_size, quality=self.quality,
                             bg_color=self.bg_color, tone=self.tone, brand=self.brand,
                             adjust=self.adjust)
            self.composite_done.emit(str(result))
        except Exception as e:  # noqa: BLE001
            self.composite_failed.emit(str(e))
