from ui.slot_editor import SlotEditor

SLOTS = [{"x": 0, "y": 0, "w": 100, "h": 100}, {"x": 100, "y": 0, "w": 100, "h": 100},
         {"x": 0, "y": 100, "w": 100, "h": 100}, {"x": 100, "y": 100, "w": 100, "h": 100}]


def test_slot_editor_roundtrip(qapp):
    ed = SlotEditor([dict(s) for s in SLOTS])
    got = ed.get_slots()
    assert len(got) == 4
    assert got[0]["w"] == 100


def test_windows_instantiate(qapp, tmp_path):
    from PIL import Image
    from ui.setup_window import SetupWindow
    from ui.shoot_window import ShootWindow
    from ui.result_window import ResultWindow
    from app.controller import AppController

    sample = tmp_path / "sample"; sample.mkdir()
    for i in range(4):
        Image.new("RGB", (100, 100), (i * 40, 0, 0)).save(sample / f"s{i}.jpg")
    cfg = {"camera": {"backend": "mock"}, "countdown_sec": 3, "trigger_key": "Space",
           "save_path": str(tmp_path / "out"), "slots": SLOTS, "template_path": ""}

    sw = SetupWindow(cfg); assert sw is not None
    ctrl = AppController(cfg, str(tmp_path / "out")); ctrl.backend.sample_dir = str(sample)
    shoot = ShootWindow(ctrl); assert shoot is not None
    res = ResultWindow()

    # QR/이미지 없이도 show_result가 안전하게 동작(경로만 세팅)
    img = tmp_path / "final.jpg"; Image.new("RGB", (200, 200), (10, 10, 10)).save(img)
    qr = tmp_path / "qr.png"; Image.new("RGB", (80, 80), (255, 255, 255)).save(qr)
    res.show_result(str(img), str(qr), "gofile")
    assert res is not None


def test_shoot_window_overlays(qapp, tmp_path):
    from PIL import Image
    from app.controller import AppController
    from ui.shoot_window import ShootWindow
    sample = tmp_path / "sample"; sample.mkdir()
    for i in range(4):
        Image.new("RGB", (100, 100), (i * 40, 0, 0)).save(sample / f"s{i}.jpg")
    cfg = {"camera": {"backend": "mock"}, "countdown_sec": 3, "trigger_key": "Space",
           "save_path": str(tmp_path / "out"), "slots": SLOTS, "template_path": ""}
    ctrl = AppController(cfg, str(tmp_path / "out")); ctrl.backend.sample_dir = str(sample)
    sw = ShootWindow(ctrl)
    sw.set_shot_count(2)      # 예외 없이 동작
    sw.show_countdown(3)
    sw.show_countdown(0)      # 숨김
    sw.set_hint("버튼을 눌러 촬영")
    assert sw.shot_count == 2
