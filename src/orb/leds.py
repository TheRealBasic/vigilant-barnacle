from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass

from .state import OrbState


@dataclass
class LedConfig:
    count: int
    pin: int
    brightness: float
    dma: int
    freq_hz: int
    invert: bool


class OrbLEDController:
    def __init__(self, config: LedConfig, dry_run: bool = False) -> None:
        self._config = config
        self._state = OrbState.AMBIENT
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._speak_level = 0.0
        self._dry_run = dry_run
        self._pixels = None

        if not dry_run:
            import rpi_ws281x

            self._pixels = rpi_ws281x.PixelStrip(
                num=config.count,
                pin=config.pin,
                freq_hz=config.freq_hz,
                dma=config.dma,
                invert=config.invert,
                brightness=max(0, min(255, int(config.brightness * 255))),
                channel=0,
            )
            self._pixels.begin()
        else:
            logging.info("LED dry-run: animations logged only.")

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._fill(0, 0, 0)

    def set_state(self, state: OrbState) -> None:
        self._state = state

    def set_speaking_level(self, level: float) -> None:
        self._speak_level = max(0.0, min(1.0, level))

    def _run(self) -> None:
        t = 0.0
        while not self._stop.is_set():
            if self._state == OrbState.AMBIENT:
                self._ambient_frame(t)
            elif self._state == OrbState.LISTENING:
                self._listening_frame(t)
            elif self._state == OrbState.SPEAKING:
                self._speaking_frame(t)
            elif self._state == OrbState.ERROR:
                self._error_frame(t)
            else:
                self._fill(6, 10, 12)
            t += 0.05
            time.sleep(0.05)

    def _ambient_frame(self, t: float) -> None:
        for i in range(self._config.count):
            phase = (i / max(1, self._config.count)) * math.tau
            ripple = 0.5 + 0.5 * math.sin(phase + t * 0.8)
            r = int(2 + 8 * ripple)
            g = int(22 + 25 * ripple)
            b = int(26 + 40 * ripple)
            self._set_pixel(i, r, g, b)
        self._show()

    def _listening_frame(self, t: float) -> None:
        breathe = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2.2))
        color = (int(8 * breathe), int(45 * breathe), int(55 * breathe))
        self._fill(*color)

    def _speaking_frame(self, t: float) -> None:
        amplitude = 0.2 + 0.8 * self._speak_level
        for i in range(self._config.count):
            wave = 0.5 + 0.5 * math.sin((i / self._config.count) * math.tau - (t * 4.5))
            intensity = (0.25 + 0.75 * wave) * amplitude
            self._set_pixel(i, int(6 * intensity), int(40 * intensity), int(56 * intensity))
        self._show()

    def _error_frame(self, t: float) -> None:
        blink = 1.0 if int(t * 6) % 2 == 0 else 0.1
        self._fill(int(35 * blink), int(8 * blink), int(8 * blink))

    def _fill(self, r: int, g: int, b: int) -> None:
        for i in range(self._config.count):
            self._set_pixel(i, r, g, b)
        self._show()

    def _set_pixel(self, idx: int, r: int, g: int, b: int) -> None:
        if self._dry_run:
            return
        import rpi_ws281x

        assert self._pixels is not None
        self._pixels.setPixelColor(idx, rpi_ws281x.Color(r, g, b))

    def _show(self) -> None:
        if self._dry_run:
            return
        assert self._pixels is not None
        self._pixels.show()
