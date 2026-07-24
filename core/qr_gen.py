from pathlib import Path
import qrcode


def make_qr(url: str, out_path: str, box_size: int = 10) -> Path:
    if not url:
        raise ValueError("url must not be empty")
    qr = qrcode.QRCode(box_size=box_size, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def _wifi_escape(s: str) -> str:
    # WIFI: 규격 특수문자 이스케이프( \ ; , : " )
    for ch in ('\\', ';', ',', ':', '"'):
        s = s.replace(ch, '\\' + ch)
    return s


def wifi_qr_payload(ssid: str, password: str, security: str = "WPA") -> str:
    """폰 카메라가 '이 네트워크에 연결'을 띄우는 표준 WiFi 접속 QR 문자열."""
    sec = "nopass" if not password else security
    return f"WIFI:T:{sec};S:{_wifi_escape(ssid)};P:{_wifi_escape(password)};;"


def make_wifi_qr(ssid: str, password: str, out_path: str,
                 security: str = "WPA", box_size: int = 10) -> Path:
    if not ssid:
        raise ValueError("ssid must not be empty")
    return make_qr(wifi_qr_payload(ssid, password, security), out_path, box_size)
