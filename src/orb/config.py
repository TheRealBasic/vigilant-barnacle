from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrbConfig":
        return cls(
            stop_keyword=data["stop_keyword"],
            ambient_volume_normal=int(data["ambient_volume_normal"]),
            ambient_volume_ducked=int(data["ambient_volume_ducked"]),
            silence_seconds=float(data["silence_seconds"]),
            max_record_seconds=float(data["max_record_seconds"]),
            silence_threshold_multiplier=float(data.get("silence_threshold_multiplier", 1.8)),
            gpio_pin_touch=int(data["gpio_pin_touch"]),
            touch_bounce_seconds=float(data.get("touch_bounce_seconds", 0.25)),
            led_count=int(data["led_count"]),
            led_pin=int(data["led_pin"]),
            led_brightness=float(data["led_brightness"]),
            led_dma=int(data.get("led_dma", 10)),
            led_freq_hz=int(data.get("led_freq_hz", 800000)),
            led_invert=bool(data.get("led_invert", False)),
            record_sample_rate=int(data.get("record_sample_rate", 16000)),
            record_channels=int(data.get("record_channels", 1)),
            record_blocksize=int(data.get("record_blocksize", 1024)),
            ambient_fade_step=int(data.get("ambient_fade_step", 1)),
            ambient_fade_interval=float(data.get("ambient_fade_interval", 0.08)),
            chat_system_prompt=data["chat_system_prompt"],
            models=ModelConfig(**data["models"]),
            paths=PathConfig(**data["paths"]),
            dry_run=DryRunConfig(**data.get("dry_run", {})),
        )


def load_config(path: str | Path) -> OrbConfig:
    with Path(path).open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return OrbConfig.from_dict(raw)
