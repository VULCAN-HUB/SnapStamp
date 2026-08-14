"""손님 폰이 접속할 이 PC의 주소를 자동으로 고른다.

**손님 폰은 무선으로만 붙는다** — 유선 랜은 폰이 꽂을 수 없다. 그래서 "인터넷이 나가는 주소"가
아니라 **폰이 실제로 붙을 수 있는 망의 주소**를 골라야 한다. 우선순위는 그래서 이렇다.

    1) 모바일 핫스팟   손님이 이 PC가 만든 망에 직접 붙는다 (Windows: 192.168.137.1)
    2) 무선 랜(Wi-Fi)  손님이 같은 공유기 Wi-Fi 에 붙으면 도달한다
    3) 유선 랜         그 공유기에 Wi-Fi 가 함께 있을 때만 도달한다(폰은 유선 불가) → 최후 후보
    4) 없음            손님에게 줄 방법이 없다 → 화면에 안내

⚠️ 기본 라우트(인터넷 경로) 하나만 보고 고르면, 유선으로 인터넷을 쓰면서 핫스팟으로 손님을 받는
흔한 부스 구성에서 **유선 주소가 박힌 QR** 이 나가 손님이 접속하지 못한다.

인터페이스 종류 판별은 Windows `GetAdaptersAddresses`(iphlpapi) 를 ctypes 로 직접 부른다 —
추가 의존성도, 로케일 타는 명령 출력 파싱도 없다. 실패하거나 다른 OS면 주소 대역 규칙으로 물러선다.
"""
import ctypes
import socket
import sys
from ctypes import wintypes

HOTSPOT_PREFIX = "192.168.137."      # Windows 모바일 핫스팟 고정 대역

KIND_HOTSPOT, KIND_WIFI, KIND_WIRED, KIND_OTHER, KIND_NONE = (
    "핫스팟", "WiFi", "유선", "기타", "없음")
_ORDER = {KIND_HOTSPOT: 0, KIND_WIFI: 1, KIND_WIRED: 2, KIND_OTHER: 3}

_IF_TYPE_ETHERNET = 6
_IF_TYPE_WIFI = 71
_IF_TYPE_LOOPBACK = 24
_AF_INET = 2
_GAA_FLAG_SKIP_ANYCAST = 0x02
_GAA_FLAG_SKIP_MULTICAST = 0x04
_GAA_FLAG_SKIP_DNS_SERVER = 0x08


def is_private(ip: str) -> bool:
    return (ip.startswith("192.168.") or ip.startswith("10.")
            or any(ip.startswith(f"172.{i}.") for i in range(16, 32)))


class _SOCKADDR(ctypes.Structure):
    _fields_ = [("sa_family", wintypes.USHORT), ("sa_data", ctypes.c_byte * 26)]


class _SOCKET_ADDRESS(ctypes.Structure):
    _fields_ = [("lpSockaddr", ctypes.POINTER(_SOCKADDR)), ("iSockaddrLength", ctypes.c_int)]


class _IP_ADAPTER_UNICAST_ADDRESS(ctypes.Structure):
    pass


_IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
    ("Length", wintypes.ULONG), ("Flags", wintypes.DWORD),
    ("Next", ctypes.POINTER(_IP_ADAPTER_UNICAST_ADDRESS)),
    ("Address", _SOCKET_ADDRESS),
    ("PrefixOrigin", ctypes.c_int), ("SuffixOrigin", ctypes.c_int),
    ("DadState", ctypes.c_int),
    ("ValidLifetime", wintypes.ULONG), ("PreferredLifetime", wintypes.ULONG),
    ("LeaseLifetime", wintypes.ULONG), ("OnLinkPrefixLength", ctypes.c_ubyte),
]


class _IP_ADAPTER_ADDRESSES(ctypes.Structure):
    pass


# ⚠️ 앞부분 필드 순서·타입이 헤더(iptypes.h)와 어긋나면 엉뚱한 값을 읽는다.
#    쓰는 것은 Next / Union(IfIndex) / FirstUnicastAddress / IfType / OperStatus 뿐이지만,
#    그 앞의 필드를 하나라도 빠뜨리면 오프셋이 밀리므로 순서대로 전부 선언한다.
_IP_ADAPTER_ADDRESSES._fields_ = [
    ("Length", wintypes.ULONG), ("IfIndex", wintypes.DWORD),
    ("Next", ctypes.POINTER(_IP_ADAPTER_ADDRESSES)),
    ("AdapterName", ctypes.c_char_p),
    ("FirstUnicastAddress", ctypes.POINTER(_IP_ADAPTER_UNICAST_ADDRESS)),
    ("FirstAnycastAddress", ctypes.c_void_p),
    ("FirstMulticastAddress", ctypes.c_void_p),
    ("FirstDnsServerAddress", ctypes.c_void_p),
    ("DnsSuffix", ctypes.c_wchar_p), ("Description", ctypes.c_wchar_p),
    ("FriendlyName", ctypes.c_wchar_p),
    ("PhysicalAddress", ctypes.c_ubyte * 8), ("PhysicalAddressLength", wintypes.DWORD),
    ("Flags", wintypes.DWORD), ("Mtu", wintypes.DWORD),
    ("IfType", wintypes.DWORD), ("OperStatus", ctypes.c_int),
]


def _windows_candidates():
    """[(ip, kind, friendly_name)] — 살아 있는(OperStatus=Up) IPv4 인터페이스만."""
    size = wintypes.ULONG(15000)
    buf = ctypes.create_string_buffer(size.value)
    flags = _GAA_FLAG_SKIP_ANYCAST | _GAA_FLAG_SKIP_MULTICAST | _GAA_FLAG_SKIP_DNS_SERVER
    ret = ctypes.windll.iphlpapi.GetAdaptersAddresses(
        _AF_INET, flags, None, ctypes.byref(buf), ctypes.byref(size))
    if ret == 111:                      # ERROR_BUFFER_OVERFLOW — 알려준 크기로 재시도
        buf = ctypes.create_string_buffer(size.value)
        ret = ctypes.windll.iphlpapi.GetAdaptersAddresses(
            _AF_INET, flags, None, ctypes.byref(buf), ctypes.byref(size))
    if ret != 0:
        return []
    out = []
    node = ctypes.cast(buf, ctypes.POINTER(_IP_ADAPTER_ADDRESSES))
    while node:
        a = node.contents
        if a.OperStatus == 1 and a.IfType != _IF_TYPE_LOOPBACK:   # 1 = IfOperStatusUp
            ua = a.FirstUnicastAddress
            while ua:
                sa = ua.contents.Address.lpSockaddr.contents
                if sa.sa_family == _AF_INET:
                    ip = ".".join(str(b & 0xFF) for b in sa.sa_data[2:6])
                    if not ip.startswith("127.") and not ip.startswith("169.254."):
                        out.append((ip, _kind_of(ip, a.IfType), a.FriendlyName or ""))
                ua = ua.contents.Next
        node = a.Next
    return out


def _kind_of(ip: str, if_type: int) -> str:
    if ip.startswith(HOTSPOT_PREFIX):
        return KIND_HOTSPOT          # 대역이 곧 증거 — 핫스팟은 어댑터 종류가 무선으로 안 잡힐 때가 있다
    if if_type == _IF_TYPE_WIFI:
        return KIND_WIFI
    if if_type == _IF_TYPE_ETHERNET:
        return KIND_WIRED
    return KIND_OTHER


def _fallback_candidates():
    """Windows API 를 못 쓸 때 — 종류를 모르니 대역만 보고 나눈다."""
    out = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            if any(ip == c[0] for c in out):
                continue
            out.append((ip, KIND_HOTSPOT if ip.startswith(HOTSPOT_PREFIX) else KIND_OTHER, ""))
    except OSError:
        pass
    return out


def rank(cands):
    """후보를 손님 도달 가능성 순으로 정렬. 사설 주소를 공인 주소보다 앞에 둔다."""
    return sorted(cands, key=lambda c: (_ORDER.get(c[1], 9), 0 if is_private(c[0]) else 1, c[0]))


def guest_addresses():
    """[(ip, kind, name)] — 손님이 접속할 만한 주소를 좋은 순서로."""
    cands = []
    if sys.platform.startswith("win"):
        try:
            cands = _windows_candidates()
        except Exception:  # noqa: BLE001 — API 실패해도 앱은 계속 떠야 한다
            cands = []
    if not cands:
        cands = _fallback_candidates()
    return rank(cands)


def pick_guest_ip():
    """(ip, kind) — QR 에 박을 주소. 후보가 없으면 ("127.0.0.1", 없음)."""
    best = guest_addresses()
    if not best:
        return "127.0.0.1", KIND_NONE
    return best[0][0], best[0][1]
