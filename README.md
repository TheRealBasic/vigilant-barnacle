# Frutiger Aero Orb (Raspberry Pi Voice Assistant)

A touch-to-talk Raspberry Pi voice assistant with a soft **Frutiger Aero** aesthetic:
- Ambient audio loop always playing quietly.
- Aqua LED animations on a WS2812/SK6812 ring.
- TTP223 capacitive touch trigger (optional when wake-word mode is enabled).
- Optional wake-word trigger (mock engine included for development/testing).
- OpenAI speech-to-text, chat, and text-to-speech.
- Headless operation on Raspberry Pi OS.
- Dry-run mode for development on a laptop/desktop.

## Project Layout

```text
.
├── assets/
│   ├── ambient_loop.ogg        # add your own file
│   ├── glass_chime.wav         # add your own file
│   └── down_chime.wav          # add your own file
├── config.yaml
├── requirements.txt
└── src/orb/
    ├── __init__.py
    ├── audio.py
    ├── config.py
    ├── gpio.py
    ├── leds.py
    ├── main.py
    ├── openai_client.py
    ├── state.py
    └── web.py
```

## Hardware Wiring Notes

### 1) TTP223 capacitive touch sensor
- **VCC** -> Pi **3.3V**
- **GND** -> Pi **GND**
- **OUT** -> Pi GPIO from `gpio_pin_touch` (default: **GPIO17**, physical pin 11)

### 2) WS2812B / SK6812 LED ring
- **DIN** -> Pi GPIO from `led_pin` (default: **GPIO18**, physical pin 12)
- **VCC** -> 5V power supply (sized for LED count)
- **GND** -> common ground with Raspberry Pi

> Recommended for stability: use a proper level shifter (3.3V->5V) on DIN and a 330Ω data resistor.

## Software Setup (Raspberry Pi OS)

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv mpv libportaudio2 libsndfile1
```

Create and activate venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Run tests

After installing dependencies, run the pure-Python test suite from repo root:

```bash
PYTHONPATH=src pytest -q
```

## OpenAI API key

```bash
export OPENAI_API_KEY="your_api_key_here"
```

Persist across boots (optional):

```bash
echo 'export OPENAI_API_KEY="your_api_key_here"' >> ~/.bashrc
```

## Add required audio assets

Place your files here:
- `assets/ambient_loop.ogg`
- `assets/glass_chime.wav`
- `assets/down_chime.wav`

## Configure Orb

Edit `config.yaml` to tune:
- stop keyword (`stop_keyword`)
- ambient volumes (`ambient_volume_normal`, `ambient_volume_ducked`)
- silence detection and max record seconds
- GPIO pin and LED setup
- OpenAI model names

## Run

From repo root:

```bash
PYTHONPATH=src python -m orb.main --config config.yaml
```

Dry run (no GPIO/LED hardware):
- Press `ENTER` to simulate touch
- If wake-word is enabled with `engine: mock`, type the wake word and press `ENTER`


```bash
PYTHONPATH=src python -m orb.main --config config.yaml --dry-run
```

## Wake-word mode

Add this section to `config.yaml` to enable wake-word triggering:

```yaml
wake_word:
  enabled: true
  keyword: "orb"
  engine: "mock"
  sensitivity: null
  threshold: null
  allow_touch: true
```

Notes:
- `enabled: true` starts the wake-word listener.
- `allow_touch: true` keeps touch enabled too, so either trigger can start a session.
- `engine: mock` is a built-in development engine; in dry-run, entering the keyword triggers a session.
- `sensitivity` and `threshold` are optional tuning values for future/engine-specific implementations.


## Local Web API (optional)

Orb can expose a small HTTP control/status API for local integrations.

Security note:
- Keep `web.host` bound to `127.0.0.1` by default.
- Do **not** expose this API publicly without adding your own auth/proxy controls.

Config snippet:

```yaml
web:
  enabled: true
  host: "127.0.0.1"
  port: 8765
```

Example usage:

```bash
# Health and state
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/state

# Trigger an interaction
curl -s -X POST http://127.0.0.1:8765/actions/trigger

# Toggle simulation mode
curl -s -X POST http://127.0.0.1:8765/actions/simulation \
  -H 'Content-Type: application/json' \
  -d '{"enabled": true}'

# Reset conversation
curl -s -X POST http://127.0.0.1:8765/actions/reset
```

API behavior notes:
- State payload returns only summaries of transcript/reply text.
- Full transcript content and API key data are intentionally not exposed.

## Runtime behavior

1. **Ambient mode**
   - Ambient loop plays continuously (~15% volume by default).
   - LED ring shows slow aqua drift.

2. **Trigger-to-talk**
   - On touch or wake-word (depending on config): glass chime, LEDs breathe cyan, ambient ducks to ~6%.
   - Mic recording starts immediately.
   - Rapid repeated detections are deduplicated to prevent overlapping sessions.

3. **Stop listening**
   - Stop when silence persists for `silence_seconds`.
   - Or when `max_record_seconds` is reached.
   - If transcript contains `stop_keyword`, assistant cancels response and returns ambient mode.

4. **Reply**
   - Transcript -> OpenAI chat -> OpenAI TTS.
   - While speaking, LEDs animate a wave synced to reply RMS.
   - Ambient remains ducked during speech.
   - Ambient fades back to normal after playback.


## Windows SD-card staging setup

If you want to prepare a deploy bundle on a Windows machine *before* moving it to an SD card, use the included PowerShell script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows-sd-staging.ps1 `
  -ProjectRoot . `
  -OutputDir sd_staging `
  -StopKeyword "orb sleep" `
  -EnableWakeWord `
  -WakeWord "orb"
```

What it does:
- Verifies required audio files exist in `assets/`.
- Copies `config.yaml` and updates `stop_keyword` + wake-word settings.
- Copies required audio assets into a staging folder.
- Creates `orb.env` containing your OpenAI API key.
- Writes a short transfer guide at `sd_staging/README-WINDOWS-STAGING.txt`.

Output layout:

```text
sd_staging/
├── README-WINDOWS-STAGING.txt
└── orb/
    ├── config.yaml
    ├── orb.env
    └── assets/
        ├── ambient_loop.ogg
        ├── glass_chime.wav
        └── down_chime.wav
```

After copying to the Pi, continue with the Linux setup and runtime steps in this README.

## Troubleshooting

### ALSA input/output device issues
List devices:

```bash
arecord -l
aplay -l
```

Check default capture/playback from Python:

```bash
python - <<'PY'
import sounddevice as sd
print(sd.query_devices())
print('Default:', sd.default.device)
PY
```

If needed, create/edit `~/.asoundrc` to set default card/device.

### mpv IPC socket errors
- Ensure no stale socket file exists at `paths.mpv_socket`.
- Confirm `mpv` is installed and runnable.

### LED not lighting
- Confirm `led_pin` matches your wiring.
- Use external 5V power and common ground.
- Verify `rpi_ws281x` support for your Pi/kernel setup.

### Permission issues with GPIO/LED
Run as a user with GPIO access (often `pi`) and try:

```bash
sudo usermod -aG gpio $USER
```

Log out/in after group changes.

## Notes
- This app is **not always listening** for full speech; it records only after a configured trigger (touch and/or wake-word).
- Network/API failures are handled gracefully: down chime, ambient restore, continue running.
- Console logs include timestamps for headless debugging.
