from __future__ import annotations

import json
import urllib.request

from orb.state import OrbState
from orb.web import OrbWebServer, OrbWebStatus


def _json_request(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=2.0) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def test_web_server_endpoints_and_actions() -> None:
    status = OrbWebStatus(dry_run=True)
    status.set_state(OrbState.PROCESSING)
    status.set_ambient_running(True)
    status.set_last_transcript("hello hello hello " * 20)
    status.set_last_reply("hi there")

    calls = {"trigger": 0, "reset": 0, "simulation": None}

    server = OrbWebServer(
        host="127.0.0.1",
        port=0,
        status=status,
        trigger_interaction=lambda: calls.__setitem__("trigger", calls["trigger"] + 1),
        reset_conversation=lambda: calls.__setitem__("reset", calls["reset"] + 1),
        set_simulation_enabled=lambda enabled: calls.__setitem__("simulation", enabled),
    )

    server.start()
    assert server._httpd is not None
    base = f"http://127.0.0.1:{server._httpd.server_port}"

    try:
        health = _json_request(f"{base}/health")
        assert health == {
            "ok": True,
            "ambient_running": True,
            "last_error": None,
        }

        state = _json_request(f"{base}/state")
        assert state["state"] == "processing"
        assert state["dry_run"] is True
        assert state["simulation_enabled"] is False
        assert "chars=" in state["last_transcript_summary"]
        assert "hello hello" in state["last_transcript_summary"]
        assert "hi there" in state["last_reply_summary"]

        trigger = _json_request(f"{base}/actions/trigger", method="POST", payload={})
        assert trigger == {"triggered": True}
        assert calls["trigger"] == 1

        reset = _json_request(f"{base}/actions/reset", method="POST", payload={})
        assert reset == {"reset": True}
        assert calls["reset"] == 1

        simulation = _json_request(f"{base}/actions/simulation", method="POST", payload={"enabled": True})
        assert simulation == {"simulation_enabled": True}
        assert calls["simulation"] is True
    finally:
        server.stop()


def test_web_status_snapshot_mapping() -> None:
    status = OrbWebStatus(dry_run=False)
    status.set_state(OrbState.ERROR)
    status.set_ambient_running(False)
    status.set_simulation_enabled(True)
    status.set_last_error("boom")

    snapshot = status.snapshot()

    assert snapshot.state == OrbState.ERROR
    assert snapshot.ambient_running is False
    assert snapshot.dry_run is False
    assert snapshot.simulation_enabled is True
    assert snapshot.last_error == "boom"
