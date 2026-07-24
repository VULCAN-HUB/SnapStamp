from enum import Enum, auto


class AppState(Enum):
    SETUP = auto()
    IDLE = auto()
    COUNTDOWN = auto()
    SHOOTING = auto()
    PREVIEW = auto()
    COMPOSITING = auto()
    RESULT = auto()
    PROMPT = auto()
