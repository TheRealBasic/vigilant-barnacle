from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest


# Avoid requiring native PortAudio during test collection.
sys.modules.setdefault("sounddevice", SimpleNamespace())

main = importlib.import_module("orb.main")


class _OneShotEvent:
    def __init__(self) -> None:
        self._wait_calls = 0

    def is_set(self) -> bool:
        return False

    def set(self) -> None:
        return None

    def wait(self) -> None:
        self._wait_calls += 1
        if self._wait_calls > 1:
            raise KeyboardInterrupt

    def clear(self) -> None:
        return None


class _DummyTouch:
    def __init__(self) -> None:
        self.started = False

    def start(self, _callback) -> None:
        self.started = True
        return None

    def stop(self) -> None:
        return None


class _RecordingInput:
    def __init__(self, label: str, sink: list[str]) -> None:
        self.label = label
        self.sink = sink

    def start(self, callback) -> None:
        self.sink.append(self.label)
        self.callback = callback

    def stop(self) -> None:
        return None


class _DummyAmbient:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def fade_to(self, _target: int) -> None:
        return None


class _DummyLEDs:
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def set_state(self, _state) -> None:
        return None

    def set_speaking_level(self, _level: float) -> None:
        return None


class _DummyAudio:
    def __init__(self) -> None:
        self.cleanup_calls: list[str] = []

    def play_file_blocking(self, _path: str) -> None:
        return None

    def record_until_stop(self, **_kwargs):
        return SimpleNamespace(wav_path="/tmp/orb-recording.wav")

    def cleanup_file(self, path: str) -> None:
        self.cleanup_calls.append(path)


class _DummyAI:
    def __init__(self, fail_step: str) -> None:
        self.fail_step = fail_step

    def transcribe(self, _wav_path: str, _model: str) -> str:
        if self.fail_step == "transcribe":
            raise RuntimeError("transcribe boom")
        return "hello orb"

    def chat(self, _messages, model: str) -> str:
        if self.fail_step == "chat":
            raise RuntimeError("chat boom")
        return "hello back"

    def tts(self, _reply: str, _model: str, _output_path: str) -> str:
        if self.fail_step == "tts":
            raise RuntimeError("tts boom")
        return "/tmp/reply.mp3"


@pytest.mark.parametrize("fail_step", ["transcribe", "chat", "tts"])
def test_run_cleans_up_recording_when_interaction_raises(monkeypatch: pytest.MonkeyPatch, tmp_path, fail_step: str) -> None:
    audio = _DummyAudio()

    cfg = SimpleNamespace(
        dry_run=SimpleNamespace(enabled=True),
        paths=SimpleNamespace(
            tts_output=str(tmp_path / "tts" / "reply.mp3"),
            glass_chime="glass.wav",
            down_chime="down.wav",
            ambient_loop="ambient.ogg",
            mpv_socket=str(tmp_path / "mpv.sock"),
        ),
        led_count=16,
        led_pin=18,
        led_brightness=0.2,
        led_dma=10,
        led_freq_hz=800000,
        led_invert=False,
        gpio_pin_touch=17,
        touch_bounce_seconds=0.05,
        ambient_volume_normal=20,
        ambient_volume_ducked=6,
        ambient_fade_step=1,
        ambient_fade_interval=0.01,
        record_sample_rate=16000,
        record_channels=1,
        record_blocksize=1024,
        silence_seconds=1.0,
        max_record_seconds=4.0,
        silence_threshold_multiplier=1.3,
        stop_keyword="stop",
        chat_system_prompt="You are Orb.",
        models=SimpleNamespace(transcribe="m1", chat="m2", tts="m3"),
        wake_word=SimpleNamespace(enabled=False, keyword="orb", engine="mock", allow_touch=True),
        conversation=SimpleNamespace(enabled=False, max_turns=6, reset_timeout_seconds=None),
    )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main.argparse.ArgumentParser, "parse_args", lambda self: SimpleNamespace(config="x", dry_run=True))
    monkeypatch.setattr(main, "load_config", lambda _path: cfg)
    monkeypatch.setattr(main.threading, "Event", _OneShotEvent)
    monkeypatch.setattr(main, "build_touch_input", lambda **_kwargs: _DummyTouch())
    monkeypatch.setattr(main, "build_wake_word_input", lambda **_kwargs: _DummyTouch())
    monkeypatch.setattr(main, "AmbientPlayer", lambda **_kwargs: _DummyAmbient())
    monkeypatch.setattr(main, "AudioIO", lambda **_kwargs: audio)
    monkeypatch.setattr(main, "OrbOpenAIClient", lambda: _DummyAI(fail_step=fail_step))
    monkeypatch.setattr(main, "OrbLEDController", lambda *_args, **_kwargs: _DummyLEDs())
    monkeypatch.setattr(main, "play_with_led_sync", lambda *_args, **_kwargs: None)

    main.run()

    assert audio.cleanup_calls == ["/tmp/orb-recording.wav"]


@pytest.mark.parametrize(
    ("wake_enabled", "allow_touch", "expected"),
    [
        (False, True, ["touch"]),
        (True, False, ["wake"]),
        (True, True, ["touch", "wake"]),
    ],
)
def test_run_selects_trigger_sources(monkeypatch: pytest.MonkeyPatch, tmp_path, wake_enabled: bool, allow_touch: bool, expected: list[str]) -> None:
    started: list[str] = []

    cfg = SimpleNamespace(
        dry_run=SimpleNamespace(enabled=True),
        paths=SimpleNamespace(
            tts_output=str(tmp_path / "tts" / "reply.mp3"),
            glass_chime="glass.wav",
            down_chime="down.wav",
            ambient_loop="ambient.ogg",
            mpv_socket=str(tmp_path / "mpv.sock"),
        ),
        led_count=16,
        led_pin=18,
        led_brightness=0.2,
        led_dma=10,
        led_freq_hz=800000,
        led_invert=False,
        gpio_pin_touch=17,
        touch_bounce_seconds=0.05,
        ambient_volume_normal=20,
        ambient_volume_ducked=6,
        ambient_fade_step=1,
        ambient_fade_interval=0.01,
        record_sample_rate=16000,
        record_channels=1,
        record_blocksize=1024,
        silence_seconds=1.0,
        max_record_seconds=4.0,
        silence_threshold_multiplier=1.3,
        stop_keyword="stop",
        chat_system_prompt="You are Orb.",
        models=SimpleNamespace(transcribe="m1", chat="m2", tts="m3"),
        wake_word=SimpleNamespace(enabled=wake_enabled, keyword="orb", engine="mock", allow_touch=allow_touch),
        conversation=SimpleNamespace(enabled=False, max_turns=6, reset_timeout_seconds=None),
    )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main.argparse.ArgumentParser, "parse_args", lambda self: SimpleNamespace(config="x", dry_run=True))
    monkeypatch.setattr(main, "load_config", lambda _path: cfg)
    monkeypatch.setattr(main.threading, "Event", _OneShotEvent)
    monkeypatch.setattr(main, "build_touch_input", lambda **_kwargs: _RecordingInput("touch", started))
    monkeypatch.setattr(main, "build_wake_word_input", lambda **_kwargs: _RecordingInput("wake", started))
    monkeypatch.setattr(main, "AmbientPlayer", lambda **_kwargs: _DummyAmbient())
    monkeypatch.setattr(main, "AudioIO", lambda **_kwargs: _DummyAudio())
    monkeypatch.setattr(main, "OrbOpenAIClient", lambda: _DummyAI(fail_step="none"))
    monkeypatch.setattr(main, "OrbLEDController", lambda *_args, **_kwargs: _DummyLEDs())
    monkeypatch.setattr(main, "play_with_led_sync", lambda *_args, **_kwargs: None)

    main.run()

    assert started == expected


def test_touch_event_deduplicates_triggers() -> None:
    event = main.threading.Event()

    def on_touch() -> None:
        if not event.is_set():
            event.set()

    on_touch()
    on_touch()

    assert event.is_set()

class _FixedIterationsEvent:
    def __init__(self, iterations: int) -> None:
        self._remaining = iterations

    def is_set(self) -> bool:
        return False

    def set(self) -> None:
        return None

    def wait(self) -> None:
        if self._remaining <= 0:
            raise KeyboardInterrupt
        self._remaining -= 1

    def clear(self) -> None:
        return None


class _SequenceAudio(_DummyAudio):
    def __init__(self, turns: int) -> None:
        super().__init__()
        self._turns = turns

    def record_until_stop(self, **_kwargs):
        self._turns -= 1
        return SimpleNamespace(wav_path=f"/tmp/orb-recording-{self._turns}.wav")


class _ConversationAwareAI:
    def __init__(self, transcripts: list[str]) -> None:
        self._transcripts = transcripts
        self.chat_messages: list[list[dict[str, str]]] = []

    def transcribe(self, _wav_path: str, _model: str) -> str:
        return self._transcripts.pop(0)

    def chat(self, messages, model: str) -> str:
        self.chat_messages.append(messages)
        return "reply"

    def tts(self, _reply: str, _model: str, _output_path: str) -> str:
        return "/tmp/reply.mp3"


def test_run_resets_conversation_on_stop_keyword(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    ai = _ConversationAwareAI(["hello", "orb sleep", "hello again"])

    cfg = SimpleNamespace(
        dry_run=SimpleNamespace(enabled=True),
        paths=SimpleNamespace(
            tts_output=str(tmp_path / "tts" / "reply.mp3"),
            glass_chime="glass.wav",
            down_chime="down.wav",
            ambient_loop="ambient.ogg",
            mpv_socket=str(tmp_path / "mpv.sock"),
        ),
        led_count=16,
        led_pin=18,
        led_brightness=0.2,
        led_dma=10,
        led_freq_hz=800000,
        led_invert=False,
        gpio_pin_touch=17,
        touch_bounce_seconds=0.05,
        ambient_volume_normal=20,
        ambient_volume_ducked=6,
        ambient_fade_step=1,
        ambient_fade_interval=0.01,
        record_sample_rate=16000,
        record_channels=1,
        record_blocksize=1024,
        silence_seconds=1.0,
        max_record_seconds=4.0,
        silence_threshold_multiplier=1.3,
        stop_keyword="orb sleep",
        chat_system_prompt="You are Orb.",
        models=SimpleNamespace(transcribe="m1", chat="m2", tts="m3"),
        wake_word=SimpleNamespace(enabled=False, keyword="orb", engine="mock", allow_touch=True),
        conversation=SimpleNamespace(enabled=True, max_turns=6, reset_timeout_seconds=None),
    )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main.argparse.ArgumentParser, "parse_args", lambda self: SimpleNamespace(config="x", dry_run=True))
    monkeypatch.setattr(main, "load_config", lambda _path: cfg)
    monkeypatch.setattr(main.threading, "Event", lambda: _FixedIterationsEvent(iterations=3))
    monkeypatch.setattr(main, "build_touch_input", lambda **_kwargs: _DummyTouch())
    monkeypatch.setattr(main, "build_wake_word_input", lambda **_kwargs: _DummyTouch())
    monkeypatch.setattr(main, "AmbientPlayer", lambda **_kwargs: _DummyAmbient())
    monkeypatch.setattr(main, "AudioIO", lambda **_kwargs: _SequenceAudio(turns=3))
    monkeypatch.setattr(main, "OrbOpenAIClient", lambda: ai)
    monkeypatch.setattr(main, "OrbLEDController", lambda *_args, **_kwargs: _DummyLEDs())
    monkeypatch.setattr(main, "play_with_led_sync", lambda *_args, **_kwargs: None)

    main.run()

    assert len(ai.chat_messages) == 2
    assert ai.chat_messages[1] == [
        {"role": "system", "content": "You are Orb."},
        {"role": "user", "content": "hello again"},
    ]


def test_run_resets_conversation_on_reset_phrase(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    ai = _ConversationAwareAI(["hello", "reset conversation", "hello again"])

    cfg = SimpleNamespace(
        dry_run=SimpleNamespace(enabled=True),
        paths=SimpleNamespace(
            tts_output=str(tmp_path / "tts" / "reply.mp3"),
            glass_chime="glass.wav",
            down_chime="down.wav",
            ambient_loop="ambient.ogg",
            mpv_socket=str(tmp_path / "mpv.sock"),
        ),
        led_count=16,
        led_pin=18,
        led_brightness=0.2,
        led_dma=10,
        led_freq_hz=800000,
        led_invert=False,
        gpio_pin_touch=17,
        touch_bounce_seconds=0.05,
        ambient_volume_normal=20,
        ambient_volume_ducked=6,
        ambient_fade_step=1,
        ambient_fade_interval=0.01,
        record_sample_rate=16000,
        record_channels=1,
        record_blocksize=1024,
        silence_seconds=1.0,
        max_record_seconds=4.0,
        silence_threshold_multiplier=1.3,
        stop_keyword="orb sleep",
        chat_system_prompt="You are Orb.",
        models=SimpleNamespace(transcribe="m1", chat="m2", tts="m3"),
        wake_word=SimpleNamespace(enabled=False, keyword="orb", engine="mock", allow_touch=True),
        conversation=SimpleNamespace(enabled=True, max_turns=6, reset_timeout_seconds=None),
    )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main.argparse.ArgumentParser, "parse_args", lambda self: SimpleNamespace(config="x", dry_run=True))
    monkeypatch.setattr(main, "load_config", lambda _path: cfg)
    monkeypatch.setattr(main.threading, "Event", lambda: _FixedIterationsEvent(iterations=3))
    monkeypatch.setattr(main, "build_touch_input", lambda **_kwargs: _DummyTouch())
    monkeypatch.setattr(main, "build_wake_word_input", lambda **_kwargs: _DummyTouch())
    monkeypatch.setattr(main, "AmbientPlayer", lambda **_kwargs: _DummyAmbient())
    monkeypatch.setattr(main, "AudioIO", lambda **_kwargs: _SequenceAudio(turns=3))
    monkeypatch.setattr(main, "OrbOpenAIClient", lambda: ai)
    monkeypatch.setattr(main, "OrbLEDController", lambda *_args, **_kwargs: _DummyLEDs())
    monkeypatch.setattr(main, "play_with_led_sync", lambda *_args, **_kwargs: None)

    main.run()

    assert len(ai.chat_messages) == 2
    assert ai.chat_messages[1] == [
        {"role": "system", "content": "You are Orb."},
        {"role": "user", "content": "hello again"},
    ]
