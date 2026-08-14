"""손님 접속 주소 자동 판정 — 유선/WiFi/오프라인 세 상황.

핵심 계약: **폰은 유선을 못 꽂는다.** 그래서 인터넷이 나가는 경로가 아니라 폰이 붙을 수 있는
무선 쪽을 먼저 고른다. 핫스팟 > Wi-Fi > 유선 > 기타.
"""
from core.net_addr import (rank, is_private, KIND_HOTSPOT, KIND_WIFI, KIND_WIRED, KIND_OTHER)


def _pick(cands):
    return rank(cands)[0][0]


def test_wired_only_still_gives_an_address():
    """유선만 연결 — 공유기에 Wi-Fi가 같이 있으면 손님이 도달할 수 있으니 주소는 준다."""
    assert _pick([("192.168.0.10", KIND_WIRED, "이더넷")]) == "192.168.0.10"


def test_wifi_beats_wired():
    """유선+Wi-Fi 동시 — 폰이 붙는 쪽은 Wi-Fi다."""
    assert _pick([("192.168.0.10", KIND_WIRED, "이더넷"),
                  ("192.168.50.10", KIND_WIFI, "Wi-Fi")]) == "192.168.50.10"


def test_hotspot_beats_everything():
    """인터넷은 유선으로 쓰고 손님은 핫스팟에 붙는 부스 구성 — 여기서 유선을 고르면 손님이 못 연다."""
    cands = [("192.168.0.10", KIND_WIRED, "이더넷"),
             ("192.168.50.10", KIND_WIFI, "Wi-Fi"),
             ("192.168.137.1", KIND_HOTSPOT, "로컬 영역 연결")]
    assert _pick(cands) == "192.168.137.1"


def test_private_wins_over_public_in_same_kind():
    assert _pick([("203.0.113.7", KIND_OTHER, ""), ("10.0.0.5", KIND_OTHER, "")]) == "10.0.0.5"


def test_private_ranges():
    assert is_private("192.168.1.2") and is_private("10.1.2.3") and is_private("172.16.0.1")
    assert not is_private("172.32.0.1") and not is_private("8.8.8.8")
