import re
import socket
import threading
from functools import partial
from urllib.parse import unquote
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

GOFILE_UPLOAD_URL = "https://store1.gofile.io/uploadFile"


class UploadError(Exception):
    pass


def _is_private(ip: str) -> bool:
    return (ip.startswith("192.168.") or ip.startswith("10.")
            or any(ip.startswith(f"172.{i}.") for i in range(16, 32)))


def get_lan_ip() -> str:
    """손님 폰이 접속할 이 PC의 주소.

    ⚠️ **폰은 유선을 꽂을 수 없다.** 인터넷이 나가는 경로(기본 라우트)를 그대로 쓰면, 유선으로
    인터넷을 쓰면서 핫스팟으로 손님을 받는 구성에서 손님이 절대 못 여는 QR 이 나간다.
    판정은 [[core.net_addr]] 이 한다 — 핫스팟 > Wi-Fi > 유선 순.
    """
    from core.net_addr import pick_guest_ip
    return pick_guest_ip()[0]


class _NoListHandler(SimpleHTTPRequestHandler):
    """디렉터리 목록 노출 차단 — 같은 망의 타인이 저장 폴더의 다른 손님 사진을
    훑어보지 못하게 한다(정확한 파일 URL로만 접근 가능). 로그도 조용히.

    추가로 `/p/<이름>` 요청이 오면 브랜딩된 '사진 받기' 페이지를 즉석 생성해 응답한다
    (HTML 파일을 따로 만들지 않아 저장 폴더가 깨끗하게 유지됨)."""
    page_provider = None

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def do_GET(self):
        if self.path.startswith("/p/") and self.page_provider is not None:
            name = unquote(self.path[3:]).split("?")[0].strip("/")
            if not re.fullmatch(r"[A-Za-z0-9_\-]{1,80}", name):   # 경로 탈출 차단
                self.send_error(404, "Not found"); return
            try:
                html = self.page_provider(name)
            except Exception:  # noqa: BLE001
                html = None
            if not html:
                self.send_error(404, "Not found"); return
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()

    def log_message(self, *args):
        pass


class LocalServer:
    def __init__(self, serve_dir: str, page_provider=None):
        self.serve_dir = serve_dir
        self.page_provider = page_provider   # (name) -> HTML 문자열
        self._httpd = None
        self._thread = None

    def start(self, port: int = 0) -> str:
        """port>0 이면 그 포트로 고정 — 앱을 다시 켜도 이전에 나눠준 QR이 계속 동작한다.
        이미 사용 중이면 자동으로 빈 포트(0)로 물러선다."""
        provider = self.page_provider
        handler_cls = type("_Handler", (_NoListHandler,), {"page_provider": staticmethod(provider)}
                           if provider else {})
        handler = partial(handler_cls, directory=self.serve_dir)
        try:
            self._httpd = ThreadingHTTPServer(("", int(port or 0)), handler)
        except OSError:
            self._httpd = ThreadingHTTPServer(("", 0), handler)   # 포트 충돌 시 자동 배정
        port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return f"http://{get_lan_ip()}:{port}/"

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


def upload_gofile(file_path: str, timeout: float = 10.0) -> str:
    try:
        with open(file_path, "rb") as fh:
            resp = requests.post(GOFILE_UPLOAD_URL, files={"file": fh}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "ok":
            raise UploadError(f"gofile status: {data.get('status')}")
        return data["data"]["downloadPage"]
    except (requests.RequestException, KeyError, ValueError) as e:
        raise UploadError(str(e)) from e


def deliver(file_path: str, serve_dir: str, timeout: float = 10.0) -> tuple[str, str]:
    try:
        return upload_gofile(file_path, timeout=timeout), "gofile"
    except UploadError:
        srv = LocalServer(serve_dir)
        base = srv.start()
        # NOTE: 로컬 폴백 서버는 호출측이 수명 관리(결과 화면 동안 유지). 여기선 URL만 구성.
        deliver._last_server = srv  # 참조 보존(GC 방지). 실제 앱은 상태에 보관.
        return base + Path(file_path).name, "local"
