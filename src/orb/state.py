from enum import Enum


class OrbState(str, Enum):
    AMBIENT = "ambient"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"
