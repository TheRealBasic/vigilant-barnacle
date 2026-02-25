from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundfile as sf


# Avoid requiring native PortAudio during test collection.
sys.modules.setdefault("sounddevice", SimpleNamespace())

AudioIO = importlib.import_module("orb.audio").AudioIO


def test_rms_from_audio_file_returns_non_empty_normalized_values(tmp_path: Path) -> None:
    sample_rate = 16000
    duration_seconds = 0.1
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    signal = 0.25 * np.sin(2 * np.pi * 440 * t)

    audio_path = tmp_path / "sample.wav"
    sf.write(audio_path, signal, sample_rate)

    values = AudioIO.rms_from_audio_file(str(audio_path), sample_count=16)

    assert values
    assert all(0.0 <= value <= 1.0 for value in values)
    assert any(value > 0.0 for value in values)
