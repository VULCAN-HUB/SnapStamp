import gc
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _cleanup_qthreads(qapp):
    # 테스트가 생성한 QThread(AppController.camera_worker 등)가 GC 시점에
    # 여전히 실행 중이면 offscreen 플랫폼에서 access violation을 유발한다.
    # __del__/GC 타이밍에 기대지 않고, 살아있는 QThread를 직접 찾아 확실히 정지시킨다.
    yield
    # 순서 중요: 살아있는 객체를 먼저 정지시킨 뒤(수신자가 유효한 상태에서
    # 큐에 쌓인 cross-thread 시그널을 flush) 마지막에 GC로 회수한다.
    # gc.collect()를 먼저 호출하면 컨트롤러가 스레드보다 먼저 회수되어
    # processEvents()가 이미 소멸된 수신자를 참조하는 큐 이벤트를 처리하며
    # access violation을 일으킬 수 있다.
    for obj in list(gc.get_objects()):
        try:
            is_thread = isinstance(obj, QThread)
        except ReferenceError:
            continue
        if is_thread and obj.isRunning():
            if hasattr(obj, "stop"):
                obj.stop()
            else:
                obj.requestInterruption()
                obj.quit()
                obj.wait(2000)
