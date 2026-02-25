from __future__ import annotations

import logging
import threading
import time
from typing import Callable


class TouchInterface:
    def start(self, callback: Callable[[], None]) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class GPIOTouchInput(TouchInterface):
    def __init__(self, pin: int, bounce_seconds: float) -> None:
        from gpiozero import Button

        self.button = Button(pin=pin, pull_up=False, bounce_time=bounce_seconds)

    def start(self, callback: Callable[[], None]) -> None:
        self.button.when_pressed = callback

    def stop(self) -> None:
        self.button.close()


class KeyboardTouchInput(TouchInterface):
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self, callback: Callable[[], None]) -> None:
        def loop() -> None:
            logging.info("Dry run enabled: press ENTER to simulate touch.")
            while not self._stop.is_set():
                try:
                    _ = input()
                except EOFError:
                    time.sleep(0.2)
                    continue
                if self._stop.is_set():
                    break
                callback()

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


def build_touch_input(dry_run: bool, pin: int, bounce_seconds: float) -> TouchInterface:
    if dry_run:
        return KeyboardTouchInput()
    return GPIOTouchInput(pin=pin, bounce_seconds=bounce_seconds)
