"""카메라가 안 붙을 때 **이유를 화면에 띄운다** — 조용한 실패 금지.

실제 사건(2026-08-11): Insta360 을 다른 프로그램(Camera Hub)이 물고 있어 스트림이 안 열렸는데,
화면엔 "카메라를 자동 연결하고 있어요…"만 계속 떠서 원인을 찾는 데 오래 걸렸다.
백엔드는 조용히 재시도만 하고 있었다.
"""
import pytest
from core.camera.ffmpeg_cam import FFmpegCameraBackend
from ui.setup_window import SetupWindow


def test_diagnose_reports_missing_device(tmp_path):
    """없는 장치 → '찾을 수 없습니다'. 사유 문구에 손쓸 방법이 들어 있어야 한다."""
    cam = FFmpegCameraBackend(str(tmp_path), device_name="존재하지않는카메라_TEST")
    msg = cam._diagnose()
    assert msg, "실패했는데 사유가 비어 있으면 화면에 띄울 것이 없다"
    assert "찾을 수 없" in msg or "열 수 없" in msg
    assert any(k in msg for k in ("케이블", "USB", "전원", "프로그램")), "해결 방법이 없다"


def test_backend_starts_with_no_error(tmp_path):
    assert FFmpegCameraBackend(str(tmp_path), device_name="x").last_error == ""


@pytest.fixture
def win(qapp):
    w = SetupWindow({"camera": {"backend": "mock"}})
    yield w
    w.close(); w.deleteLater(); qapp.processEvents()


def test_error_is_shown_on_screen(win):
    """사유가 미리보기 자리에 그대로 뜨고, 상태 배지도 '연결 실패'로 바뀐다."""
    win.set_camera_error("다른 프로그램이 카메라를 쓰고 있습니다 — Camera Hub 를 닫으세요")
    assert "다른 프로그램" in win.preview.text()
    assert "연결 실패" in win.cam_status.text()


def test_frame_clears_the_error(win, qapp):
    """다시 붙으면 안내가 사라지고 평소 화면으로 돌아온다(경고가 남아 있으면 안 된다)."""
    from PyQt5.QtGui import QImage
    win.set_camera_error("카메라를 찾을 수 없습니다")
    win.show()
    qapp.processEvents()
    win.show_preview_frame(QImage(64, 36, QImage.Format_RGB888))
    assert win.preview.text() == ""
    assert "연결됨" in win.cam_status.text()
