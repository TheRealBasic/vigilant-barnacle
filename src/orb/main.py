from __future__ import annotations

import argparse
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from .audio import AmbientPlayer, AudioIO
from .config import ConfigError, load_config
from .gpio import build_touch_input
from .leds import LedConfig, OrbLEDController
from .openai_client import OrbOpenAIClient
from .state import OrbState


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def play_with_led_sync(audio_path: str, leds: OrbLEDController, audio: AudioIO) -> None:
    levels = audio.rms_from_audio_file(audio_path)
    proc = subprocess.Popen(
        ["mpv", "--no-video", "--really-quiet", audio_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    start = time.time()
    while proc.poll() is None:
        elapsed = time.time() - start
        idx = min(int(elapsed * 20), len(levels) - 1)
        leds.set_speaking_level(levels[idx])
        time.sleep(0.05)
    leds.set_speaking_level(0.0)


def run() -> None:
    parser = argparse.ArgumentParser(description="Frutiger Aero Orb assistant")
    parser.add_argument("--config", default="config.yaml", help="Path to config yaml")
    parser.add_argument("--dry-run", action="store_true", help="Simulate GPIO and LEDs via keyboard")
    args = parser.parse_args()

    setup_logging()
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        logging.fatal("Invalid configuration: %s", exc)
        raise SystemExit(1) from exc

    dry_run = args.dry_run or cfg.dry_run.enabled

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    Path(cfg.paths.tts_output).parent.mkdir(parents=True, exist_ok=True)

    leds = OrbLEDController(
        LedConfig(
            count=cfg.led_count,
            pin=cfg.led_pin,
            brightness=cfg.led_brightness,
            dma=cfg.led_dma,
            freq_hz=cfg.led_freq_hz,
            invert=cfg.led_invert,
        ),
        dry_run=dry_run,
    )
    touch_event = threading.Event()

    def on_touch() -> None:
        if not touch_event.is_set():
            logging.info("Touch detected")
            touch_event.set()

    touch = build_touch_input(dry_run=dry_run, pin=cfg.gpio_pin_touch, bounce_seconds=cfg.touch_bounce_seconds)

    ambient = AmbientPlayer(
        loop_path=cfg.paths.ambient_loop,
        socket_path=cfg.paths.mpv_socket,
        initial_volume=cfg.ambient_volume_normal,
        fade_step=cfg.ambient_fade_step,
        fade_interval=cfg.ambient_fade_interval,
    )
    audio = AudioIO(
        sample_rate=cfg.record_sample_rate,
        channels=cfg.record_channels,
        blocksize=cfg.record_blocksize,
    )
    ai = OrbOpenAIClient()

    leds.start()
    leds.set_state(OrbState.AMBIENT)
    touch.start(on_touch)
    ambient.start()

    logging.info("Orb is running. Waiting for touch...")

    try:
        while True:
            touch_event.wait()
            touch_event.clear()

            try:
                recording = None
                ambient.fade_to(cfg.ambient_volume_ducked)
                audio.play_file_blocking(cfg.paths.glass_chime)
                leds.set_state(OrbState.LISTENING)

                recording = audio.record_until_stop(
                    silence_seconds=cfg.silence_seconds,
                    max_record_seconds=cfg.max_record_seconds,
                    threshold_multiplier=cfg.silence_threshold_multiplier,
                )

                leds.set_state(OrbState.PROCESSING)
                transcript = ai.transcribe(recording.wav_path, cfg.models.transcribe)
                logging.info("Transcript: %s", transcript or "<empty>")

                if cfg.stop_keyword.lower() in transcript.lower():
                    logging.info("Stop keyword detected. Returning to ambient mode.")
                    audio.play_file_blocking(cfg.paths.down_chime)
                    ambient.fade_to(cfg.ambient_volume_normal)
                    leds.set_state(OrbState.AMBIENT)
                    continue

                if not transcript.strip():
                    logging.info("Empty transcript. Returning to ambient mode.")
                    audio.play_file_blocking(cfg.paths.down_chime)
                    ambient.fade_to(cfg.ambient_volume_normal)
                    leds.set_state(OrbState.AMBIENT)
                    continue

                reply = ai.chat(transcript, cfg.models.chat, cfg.chat_system_prompt)
                logging.info("Assistant: %s", reply)

                tts_path = ai.tts(reply, cfg.models.tts, cfg.paths.tts_output)

                leds.set_state(OrbState.SPEAKING)
                play_with_led_sync(tts_path, leds, audio)

                ambient.fade_to(cfg.ambient_volume_normal)
                leds.set_state(OrbState.AMBIENT)
            except Exception as exc:
                logging.exception("Interaction failed: %s", exc)
                leds.set_state(OrbState.ERROR)
                audio.play_file_blocking(cfg.paths.down_chime)
                ambient.fade_to(cfg.ambient_volume_normal)
                leds.set_state(OrbState.AMBIENT)
                time.sleep(0.3)
            finally:
                if recording is not None:
                    audio.cleanup_file(recording.wav_path)

    except KeyboardInterrupt:
        logging.info("Shutting down Orb")
    finally:
        touch.stop()
        ambient.stop()
        leds.stop()


if __name__ == "__main__":
    run()
