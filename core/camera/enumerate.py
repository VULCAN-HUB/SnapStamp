"""연결된 카메라 열거. 인덱스를 순회하며 실제로 열려 유효 프레임을 주는 장치만 반환.

주의: 각 인덱스를 잠깐 열어 확인하므로 다소 느리고, 이미 다른 앱이 독점 중인
장치는 안 잡힐 수 있다. 설정 화면의 '카메라 검색' 버튼에서만 호출(시작 시 자동 X).
"""
import sys
import cv2
from core.camera.webcam import _default_capture_factory


def available_cameras(max_index: int = 6) -> list[int]:
    """열려서 유효 프레임(비검정)을 주는 카메라 인덱스 목록. webcam 백엔드와
    동일한 열기 로직(Windows=MSMF→DSHOW 폴백)을 사용해 실제 사용 가능 장치만 반환."""
    found = []
    for idx in range(max_index):
        cap = _default_capture_factory(idx)()
        try:
            if not cap.isOpened():
                continue
            ok = False
            for _ in range(5):  # 워밍업 겸 유효 프레임 확인
                r, frame = cap.read()
                if frame is not None and float(frame.mean()) > 5.0:
                    ok = True
                    break
            if ok:
                found.append(idx)
        finally:
            cap.release()
    return found
