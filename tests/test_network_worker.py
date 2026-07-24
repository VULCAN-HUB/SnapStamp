from pathlib import Path
from urllib.request import urlopen
from core import uploader
from core.workers.network_worker import NetworkWorker


def test_network_worker_cloud_when_enabled(qapp, tmp_path, monkeypatch):
    # 클라우드 옵트인(cloud_enabled=True)일 때만 외부 업로드 사용, mode="cloud".
    f = tmp_path / "final.jpg"; f.write_bytes(b"IMG")
    monkeypatch.setattr(uploader, "upload_gofile", lambda p, timeout=10.0: "https://gofile.io/d/OK")
    out = []
    w = NetworkWorker(str(f), str(tmp_path), cloud_enabled=True)
    w.delivery_done.connect(lambda url, mode: out.append((url, mode)))
    w.run()
    assert out == [("https://gofile.io/d/OK", "cloud")]


def test_network_worker_local_by_default(qapp, tmp_path, monkeypatch):
    # 기본(cloud_enabled=False)은 외부 업로드를 아예 시도하지 않고 로컬 전달.
    f = tmp_path / "final.jpg"; f.write_bytes(b"LOCAL")
    called = {"n": 0}
    monkeypatch.setattr(uploader, "upload_gofile",
                        lambda p, timeout=10.0: called.__setitem__("n", called["n"] + 1))
    out = []
    w = NetworkWorker(str(f), str(tmp_path))  # cloud_enabled 기본 False
    w.delivery_done.connect(lambda url, mode: out.append((url, mode)))
    w.run()
    assert out and out[0][1] == "local"
    assert called["n"] == 0  # 외부 업로드 시도조차 없어야 함
    w.shutdown()


def test_network_worker_local_fallback_serves_and_shutsdown(qapp, tmp_path, monkeypatch):
    f = tmp_path / "final.jpg"; f.write_bytes(b"LOCALBYTES")
    monkeypatch.setattr(uploader, "upload_gofile",
                        lambda p, timeout=10.0: (_ for _ in ()).throw(uploader.UploadError("down")))
    out = []
    w = NetworkWorker(str(f), str(tmp_path))
    w.delivery_done.connect(lambda url, mode: out.append((url, mode)))
    w.run()
    assert out and out[0][1] == "local"
    data = urlopen(out[0][0], timeout=5).read()
    assert data == b"LOCALBYTES"
    w.shutdown()  # 서버 종료 후 재요청은 실패해야 함
    import pytest, urllib.error
    with pytest.raises(urllib.error.URLError):
        urlopen(out[0][0], timeout=2)
