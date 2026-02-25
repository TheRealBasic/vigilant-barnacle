from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


@dataclass
class RecordingResult:
    wav_path: str
    seconds: float


class AmbientPlayer:
    def __init__(
        self,
        loop_path: str,
        socket_path: str,
        initial_volume: int,
        fade_step: int,
        fade_interval: float,
    ) -> None:
        self.loop_path = loop_path
        self.socket_path = socket_path
        self.volume = initial_volume
        self.fade_step = max(1, fade_step)
        self.fade_interval = fade_interval
        self.proc: subprocess.Popen[str] | None = None

    def start(self) -> None:
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        cmd = [
            "mpv",
            "--no-video",
            "--really-quiet",
            "--loop=inf",
            f"--volume={self.volume}",
            f"--input-ipc-server={self.socket_path}",
            self.loop_path,
        ]
        logging.info("Starting ambient loop: %s", self.loop_path)
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        self._wait_for_socket(timeout_s=3.0)

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

    def fade_to(self, target: int) -> None:
        target = int(max(0, min(100, target)))
        if target == self.volume:
            return
        step = self.fade_step if target > self.volume else -self.fade_step
        for v in range(self.volume, target, step):
            self._set_volume(v)
            time.sleep(self.fade_interval)
        self._set_volume(target)

    def _set_volume(self, vol: int) -> None:
        self._ipc({"command": ["set_property", "volume", int(vol)]})
        self.volume = int(vol)

    def _ipc(self, payload: dict) -> None:
        msg = (json.dumps(payload) + "\n").encode("utf-8")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(self.socket_path)
            s.sendall(msg)

    def _wait_for_socket(self, timeout_s: float) -> None:
        end = time.time() + timeout_s
        while time.time() < end:
            if os.path.exists(self.socket_path):
                return
            time.sleep(0.05)
        raise RuntimeError("Timed out waiting for mpv IPC socket")


class AudioIO:
    def __init__(self, sample_rate: int, channels: int, blocksize: int) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize

    def play_file_blocking(self, path: str) -> None:
        cmd = ["mpv", "--no-video", "--really-quiet", "--volume=100", path]
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def record_until_stop(
        self,
        silence_seconds: float,
        max_record_seconds: float,
        threshold_multiplier: float,
    ) -> RecordingResult:
        logging.info("Recording started")
        chunks: list[np.ndarray] = []
        start = time.time()
        silent_for = 0.0
        threshold = None
        calibrate_seconds = 1.0

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.blocksize,
        ) as stream:
            while True:
                data, _overflowed = stream.read(self.blocksize)
                mono = np.mean(data, axis=1)
                rms = float(np.sqrt(np.mean(np.square(mono)) + 1e-12))
                chunks.append(mono.copy())

                elapsed = time.time() - start
                if elapsed <= calibrate_seconds:
                    threshold = rms if threshold is None else (0.9 * threshold + 0.1 * rms)
                else:
                    assert threshold is not None
                    silence_threshold = threshold * threshold_multiplier
                    if rms < silence_threshold:
                        silent_for += self.blocksize / self.sample_rate
                    else:
                        silent_for = 0.0

                if elapsed >= max_record_seconds:
                    logging.info("Stopped recording: max duration reached")
                    break
                if elapsed > calibrate_seconds and silent_for >= silence_seconds:
                    logging.info("Stopped recording: silence detected")
                    break

        wav_file = tempfile.NamedTemporaryFile(prefix="orb_record_", suffix=".wav", delete=False)
        wav_path = wav_file.name
        wav_file.close()

        audio = np.concatenate(chunks, axis=0).astype(np.float32)
        sf.write(wav_path, audio, self.sample_rate)
        total_seconds = len(audio) / self.sample_rate
        logging.info("Recording saved: %s (%.2fs)", wav_path, total_seconds)
        return RecordingResult(wav_path=wav_path, seconds=total_seconds)

    @staticmethod
    def rms_from_audio_file(path: str, sample_count: int = 40) -> list[float]:
        data, sr = sf.read(path, always_2d=False)
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        window = max(1, len(data) // sample_count)
        values = []
        for i in range(0, len(data), window):
            frame = data[i : i + window]
            if len(frame) == 0:
                continue
            rms = float(np.sqrt(np.mean(np.square(frame)) + 1e-12))
            values.append(min(1.0, rms * 8.0))
        return values or [0.1]

    @staticmethod
    def cleanup_file(path: str) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception as exc:
            logging.warning("Failed to remove temp file %s: %s", path, exc)
