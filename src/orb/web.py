from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from .state import OrbState


@dataclass
class OrbWebSnapshot:
    state: OrbState
    ambient_running: bool
    dry_run: bool
    simulation_enabled: bool
    last_transcript_summary: str | None
    last_reply_summary: str | None
    last_error: str | None


class OrbWebStatus:
    def __init__(self, dry_run: bool) -> None:
        self._lock = threading.Lock()
        self._state = OrbState.AMBIENT
        self._ambient_running = False
        self._dry_run = dry_run
        self._simulation_enabled = False
        self._last_transcript_summary: str | None = None
        self._last_reply_summary: str | None = None
        self._last_error: str | None = None

    @staticmethod
    def _summarize_text(value: str, max_len: int = 80) -> str:
        normalized = " ".join(value.split())
        preview = normalized[:max_len]
        if len(normalized) > max_len:
            preview += "…"
        return f"{preview} (chars={len(value)})"

    def snapshot(self) -> OrbWebSnapshot:
        with self._lock:
            return OrbWebSnapshot(
                state=self._state,
                ambient_running=self._ambient_running,
                dry_run=self._dry_run,
                simulation_enabled=self._simulation_enabled,
                last_transcript_summary=self._last_transcript_summary,
                last_reply_summary=self._last_reply_summary,
                last_error=self._last_error,
            )

    def set_state(self, state: OrbState) -> None:
        with self._lock:
            self._state = state

    def set_ambient_running(self, running: bool) -> None:
        with self._lock:
            self._ambient_running = running

    def set_last_transcript(self, transcript: str) -> None:
        with self._lock:
            self._last_transcript_summary = self._summarize_text(transcript)

    def set_last_reply(self, reply: str) -> None:
        with self._lock:
            self._last_reply_summary = self._summarize_text(reply)

    def set_last_error(self, error: str | None) -> None:
        with self._lock:
            self._last_error = error

    def set_simulation_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._simulation_enabled = enabled


class OrbWebServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        status: OrbWebStatus,
        trigger_interaction: Callable[[], None],
        reset_conversation: Callable[[], None],
        set_simulation_enabled: Callable[[bool], None],
    ) -> None:
        self._host = host
        self._port = port
        self._status = status
        self._trigger_interaction = trigger_interaction
        self._reset_conversation = reset_conversation
        self._set_simulation_enabled = set_simulation_enabled
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._httpd is not None:
            return

        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    snap = server._status.snapshot()
                    self._json_response(
                        {
                            "ok": snap.last_error is None,
                            "ambient_running": snap.ambient_running,
                            "last_error": snap.last_error,
                        }
                    )
                    return
                if self.path == "/state":
                    snap = server._status.snapshot()
                    self._json_response(
                        {
                            "state": snap.state.value,
                            "dry_run": snap.dry_run,
                            "simulation_enabled": snap.simulation_enabled,
                            "last_transcript_summary": snap.last_transcript_summary,
                            "last_reply_summary": snap.last_reply_summary,
                        }
                    )
                    return
                self._json_response({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:  # noqa: N802
                if self.path == "/actions/trigger":
                    server._trigger_interaction()
                    self._json_response({"triggered": True})
                    return

                if self.path == "/actions/reset":
                    server._reset_conversation()
                    self._json_response({"reset": True})
                    return

                if self.path == "/actions/simulation":
                    content_len = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
                    try:
                        payload = json.loads(raw_body)
                    except json.JSONDecodeError:
                        self._json_response({"error": "invalid JSON"}, status=HTTPStatus.BAD_REQUEST)
                        return
                    enabled = bool(payload.get("enabled", False))
                    server._set_simulation_enabled(enabled)
                    self._json_response({"simulation_enabled": enabled})
                    return

                self._json_response({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                logging.debug("web: " + format, *args)

            def _json_response(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._httpd = ThreadingHTTPServer((self._host, self._port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        logging.info("Web API listening on http://%s:%s", self._host, self._port)

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._httpd = None
        self._thread = None
