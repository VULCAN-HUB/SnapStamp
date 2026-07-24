import json
from pathlib import Path

DEFAULTS = {
    "camera": {"backend": "mock", "device_index": 0, "device_name": ""},
    "template_path": "",
    # 합성 캔버스: 각 컷을 원본 1920x1080 그대로(다운스케일 없음) 2x2 배치.
    # 캔버스 3960x2280(약 9MP), 슬롯 1920x1080 = 카메라 원본 해상도 그대로 보존.
    "canvas_size": [3960, 2280],
    "slots": [
        {"x": 40, "y": 40, "w": 1920, "h": 1080},
        {"x": 2000, "y": 40, "w": 1920, "h": 1080},
        {"x": 40, "y": 1160, "w": 1920, "h": 1080},
        {"x": 2000, "y": 1160, "w": 1920, "h": 1080},
    ],
    "countdown_sec": 3,
    "photo_ratio": "original",
    "save_path": "results",
    "trigger_key": "Space",
    "qr_prompt_delay": 30,
}


def load_config(path: str | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if path and Path(path).exists():
        user = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg.update(user)
        if "camera" in user:
            merged = dict(DEFAULTS["camera"])
            merged.update(user["camera"])
            cfg["camera"] = merged
    return cfg
