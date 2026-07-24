from abc import ABC, abstractmethod
from pathlib import Path


class CameraBackend(ABC):
    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def start_liveview(self) -> None: ...

    @abstractmethod
    def stop_liveview(self) -> None: ...

    @abstractmethod
    def get_frame(self):  # -> PIL.Image.Image | None
        ...

    @abstractmethod
    def capture(self) -> Path: ...

    @property
    @abstractmethod
    def capabilities(self) -> dict: ...
