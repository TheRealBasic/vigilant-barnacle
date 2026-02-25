from __future__ import annotations

from pathlib import Path

import pytest

from orb.config import ConfigError, OrbConfig, load_config


def _valid_config_dict() -> dict:
    return {
        "stop_keyword": "stop",
        "ambient_volume_normal": 20,
        "ambient_volume_ducked": 6,
        "silence_seconds": 1.2,
        "max_record_seconds": 10,
        "gpio_pin_touch": 17,
        "led_count": 16,
        "led_pin": 18,
        "led_brightness": 0.35,
        "chat_system_prompt": "You are Orb.",
        "models": {
            "transcribe": "gpt-4o-mini-transcribe",
            "chat": "gpt-4o-mini",
            "tts": "gpt-4o-mini-tts",
        },
        "paths": {
            "ambient_loop": "assets/ambient_loop.ogg",
            "glass_chime": "assets/glass_chime.wav",
            "down_chime": "assets/down_chime.wav",
            "tts_output": "tmp/tts.mp3",
            "mpv_socket": "/tmp/mpv.sock",
        },
    }


def test_orb_config_from_dict_valid_config() -> None:
    config = OrbConfig.from_dict(_valid_config_dict())

    assert config.stop_keyword == "stop"
    assert config.ambient_volume_normal == 20
    assert config.models.chat == "gpt-4o-mini"
    assert config.paths.glass_chime.endswith("glass_chime.wav")


def test_load_config_valid_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
stop_keyword: stop
ambient_volume_normal: 20
ambient_volume_ducked: 6
silence_seconds: 1.2
max_record_seconds: 10
gpio_pin_touch: 17
led_count: 16
led_pin: 18
led_brightness: 0.35
chat_system_prompt: You are Orb.
models:
  transcribe: gpt-4o-mini-transcribe
  chat: gpt-4o-mini
  tts: gpt-4o-mini-tts
paths:
  ambient_loop: assets/ambient_loop.ogg
  glass_chime: assets/glass_chime.wav
  down_chime: assets/down_chime.wav
  tts_output: tmp/tts.mp3
  mpv_socket: /tmp/mpv.sock
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.led_brightness == pytest.approx(0.35)
    assert config.models.transcribe == "gpt-4o-mini-transcribe"


@pytest.mark.parametrize(
    "missing_key",
    [
        "stop_keyword",
        "ambient_volume_normal",
        "models",
        "paths",
    ],
)
def test_orb_config_from_dict_missing_required_keys(missing_key: str) -> None:
    data = _valid_config_dict()
    data.pop(missing_key)

    with pytest.raises(ConfigError, match=rf"config\.{missing_key} missing"):
        OrbConfig.from_dict(data)


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_message"),
    [
        ("ambient_volume_normal", 101, "ambient_volume_normal must be between 0 and 100"),
        ("ambient_volume_ducked", -1, "ambient_volume_ducked must be between 0 and 100"),
        ("led_brightness", 1.5, "led_brightness must be between 0.0 and 1.0"),
    ],
)
def test_orb_config_from_dict_invalid_numeric_ranges(
    field_name: str,
    invalid_value: float,
    expected_message: str,
) -> None:
    data = _valid_config_dict()
    data[field_name] = invalid_value

    with pytest.raises(ConfigError, match=expected_message):
        OrbConfig.from_dict(data)
