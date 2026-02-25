from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when config yaml is missing required keys or has invalid values."""


@dataclass
class ModelConfig:
    transcribe: str
    chat: str
    tts: str


@dataclass
class PathConfig:
    ambient_loop: str
    glass_chime: str
    down_chime: str
    tts_output: str
    mpv_socket: str


@dataclass
class DryRunConfig:
    enabled: bool = False


@dataclass
class OrbConfig:
    stop_keyword: str
    ambient_volume_normal: int
    ambient_volume_ducked: int
    silence_seconds: float
    max_record_seconds: float
    silence_threshold_multiplier: float
    gpio_pin_touch: int
    touch_bounce_seconds: float
    led_count: int
    led_pin: int
    led_brightness: float
    led_dma: int
    led_freq_hz: int
    led_invert: bool
    record_sample_rate: int
    record_channels: int
    record_blocksize: int
    ambient_fade_step: int
    ambient_fade_interval: float
    chat_system_prompt: str
    models: ModelConfig
    paths: PathConfig
    dry_run: DryRunConfig

    @staticmethod
    def _require_mapping(value: Any, key_path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ConfigError(f"{key_path} must be a mapping")
        return value

    @staticmethod
    def _require_key(mapping: dict[str, Any], key: str, key_path: str) -> Any:
        if key not in mapping:
            raise ConfigError(f"{key_path}.{key} missing")
        return mapping[key]

    @staticmethod
    def _require_int(value: Any, key_path: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{key_path} must be an integer") from exc

    @staticmethod
    def _require_float(value: Any, key_path: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{key_path} must be a number") from exc

    @classmethod
    def _require_positive_float(cls, value: Any, key_path: str) -> float:
        parsed = cls._require_float(value, key_path)
        if parsed <= 0:
            raise ConfigError(f"{key_path} must be > 0")
        return parsed

    @classmethod
    def _require_positive_int(cls, value: Any, key_path: str) -> int:
        parsed = cls._require_int(value, key_path)
        if parsed <= 0:
            raise ConfigError(f"{key_path} must be > 0")
        return parsed

    @classmethod
    def _require_range(cls, value: Any, key_path: str, min_value: float, max_value: float) -> float:
        parsed = cls._require_float(value, key_path)
        if not min_value <= parsed <= max_value:
            raise ConfigError(f"{key_path} must be between {min_value} and {max_value}")
        return parsed

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrbConfig":
        root = cls._require_mapping(data, "config")

        required_top_level = [
            "stop_keyword",
            "ambient_volume_normal",
            "ambient_volume_ducked",
            "silence_seconds",
            "max_record_seconds",
            "gpio_pin_touch",
            "led_count",
            "led_pin",
            "led_brightness",
            "chat_system_prompt",
            "models",
            "paths",
        ]
        for key in required_top_level:
            cls._require_key(root, key, "config")

        models_data = cls._require_mapping(root["models"], "models")
        for key in ("transcribe", "chat", "tts"):
            cls._require_key(models_data, key, "models")

        paths_data = cls._require_mapping(root["paths"], "paths")
        for key in ("ambient_loop", "glass_chime", "down_chime", "tts_output", "mpv_socket"):
            cls._require_key(paths_data, key, "paths")

        dry_run_data = root.get("dry_run", {})
        if dry_run_data is None:
            dry_run_data = {}
        dry_run_data = cls._require_mapping(dry_run_data, "dry_run")

        ambient_volume_normal = cls._require_int(root["ambient_volume_normal"], "ambient_volume_normal")
        if not 0 <= ambient_volume_normal <= 100:
            raise ConfigError("ambient_volume_normal must be between 0 and 100")

        ambient_volume_ducked = cls._require_int(root["ambient_volume_ducked"], "ambient_volume_ducked")
        if not 0 <= ambient_volume_ducked <= 100:
            raise ConfigError("ambient_volume_ducked must be between 0 and 100")

        led_brightness = cls._require_range(root["led_brightness"], "led_brightness", 0.0, 1.0)

        return cls(
            stop_keyword=str(root["stop_keyword"]),
            ambient_volume_normal=ambient_volume_normal,
            ambient_volume_ducked=ambient_volume_ducked,
            silence_seconds=cls._require_positive_float(root["silence_seconds"], "silence_seconds"),
            max_record_seconds=cls._require_positive_float(root["max_record_seconds"], "max_record_seconds"),
            silence_threshold_multiplier=cls._require_positive_float(
                root.get("silence_threshold_multiplier", 1.8), "silence_threshold_multiplier"
            ),
            gpio_pin_touch=cls._require_int(root["gpio_pin_touch"], "gpio_pin_touch"),
            touch_bounce_seconds=cls._require_positive_float(
                root.get("touch_bounce_seconds", 0.25), "touch_bounce_seconds"
            ),
            led_count=cls._require_positive_int(root["led_count"], "led_count"),
            led_pin=cls._require_int(root["led_pin"], "led_pin"),
            led_brightness=led_brightness,
            led_dma=cls._require_positive_int(root.get("led_dma", 10), "led_dma"),
            led_freq_hz=cls._require_positive_int(root.get("led_freq_hz", 800000), "led_freq_hz"),
            led_invert=bool(root.get("led_invert", False)),
            record_sample_rate=cls._require_positive_int(root.get("record_sample_rate", 16000), "record_sample_rate"),
            record_channels=cls._require_positive_int(root.get("record_channels", 1), "record_channels"),
            record_blocksize=cls._require_positive_int(root.get("record_blocksize", 1024), "record_blocksize"),
            ambient_fade_step=cls._require_positive_int(root.get("ambient_fade_step", 1), "ambient_fade_step"),
            ambient_fade_interval=cls._require_positive_float(
                root.get("ambient_fade_interval", 0.08), "ambient_fade_interval"
            ),
            chat_system_prompt=str(root["chat_system_prompt"]),
            models=ModelConfig(
                transcribe=str(models_data["transcribe"]),
                chat=str(models_data["chat"]),
                tts=str(models_data["tts"]),
            ),
            paths=PathConfig(
                ambient_loop=str(paths_data["ambient_loop"]),
                glass_chime=str(paths_data["glass_chime"]),
                down_chime=str(paths_data["down_chime"]),
                tts_output=str(paths_data["tts_output"]),
                mpv_socket=str(paths_data["mpv_socket"]),
            ),
            dry_run=DryRunConfig(enabled=bool(dry_run_data.get("enabled", False))),
        )


def load_config(path: str | Path) -> OrbConfig:
    with Path(path).open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raise ConfigError("config missing")
    return OrbConfig.from_dict(raw)
