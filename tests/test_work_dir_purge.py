"""작업 폴더의 오래된 찌꺼기는 시작할 때 정리한다 — 저장 폴더는 절대 안 건드린다.

실측(2026-08-14): 5일 사용 후 임시 폴더에 컷·QR 124개(6.8MB)가 남아 있었다.
정상 종료 때는 정리되지만 세션이 끊기거나 강제 종료되면 남는다.
"""
import os, time
from app.controller import AppController


def _aged(path, hours):
    path.write_bytes(b"x")
    old = time.time() - hours * 3600
    os.utime(path, (old, old))
    return path


def test_old_scraps_go_new_ones_stay(tmp_path, monkeypatch):
    work = tmp_path / "work"; work.mkdir()
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    old_cut = _aged(work / "shot_old.jpg", 48)
    fresh = _aged(work / "shot_new.jpg", 1)

    c = AppController({"camera": {"backend": "mock"}}, str(tmp_path / "results"))
    c.work_dir = str(work)
    c._purge_work_dir()

    assert not old_cut.exists(), "24시간 지난 임시 파일이 남았다"
    assert fresh.exists(), "최근 파일까지 지웠다(진행 중 세션이 깨진다)"


def test_results_folder_is_never_touched(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    results = tmp_path / "results"; results.mkdir()
    keep = _aged(results / "SnapStamp_old.jpg", 24 * 30)     # 한 달 전 손님 사진

    c = AppController({"camera": {"backend": "mock"}}, str(results))
    c._purge_work_dir()

    assert keep.exists(), "손님 사진을 지웠다 — 절대 안 된다"
