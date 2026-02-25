from __future__ import annotations

from orb.gpio import KeyboardWakeWordInput, NullWakeWordInput, build_wake_word_input


def test_build_wake_word_input_disabled_returns_null() -> None:
    wake = build_wake_word_input(enabled=False, dry_run=True, keyword="orb", engine="mock")

    assert isinstance(wake, NullWakeWordInput)


def test_build_wake_word_input_mock_dry_run() -> None:
    wake = build_wake_word_input(enabled=True, dry_run=True, keyword="orb", engine="mock")

    assert isinstance(wake, KeyboardWakeWordInput)


def test_build_wake_word_input_unimplemented_engine_returns_null() -> None:
    wake = build_wake_word_input(enabled=True, dry_run=False, keyword="orb", engine="porcupine")

    assert isinstance(wake, NullWakeWordInput)
