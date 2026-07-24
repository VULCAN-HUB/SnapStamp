from pathlib import Path
from urllib.request import urlopen
from core import uploader
from core.uploader import LocalServer, deliver, get_lan_ip


def test_get_lan_ip_returns_string():
    ip = get_lan_ip()
    assert isinstance(ip, str) and ip.count(".") == 3


def test_local_server_serves_file(tmp_path):
    (tmp_path / "final.jpg").write_bytes(b"HELLO-IMAGE-BYTES")
    srv = LocalServer(str(tmp_path))
    base = srv.start()
    try:
        assert base.startswith("http://")
        data = urlopen(base + "final.jpg", timeout=5).read()
        assert data == b"HELLO-IMAGE-BYTES"
    finally:
        srv.stop()


def test_deliver_falls_back_to_local_on_gofile_failure(tmp_path, monkeypatch):
    f = tmp_path / "final.jpg"; f.write_bytes(b"XYZ")

    def boom(*a, **k):
        raise uploader.UploadError("gofile down")
    monkeypatch.setattr(uploader, "upload_gofile", boom)

    url, mode = deliver(str(f), str(tmp_path))
    assert mode == "local"
    assert url.endswith("final.jpg")


def test_deliver_uses_gofile_when_available(tmp_path, monkeypatch):
    f = tmp_path / "final.jpg"; f.write_bytes(b"XYZ")
    monkeypatch.setattr(uploader, "upload_gofile", lambda p, timeout=10.0: "https://gofile.io/d/AAA")
    url, mode = deliver(str(f), str(tmp_path))
    assert mode == "gofile"
    assert url == "https://gofile.io/d/AAA"
