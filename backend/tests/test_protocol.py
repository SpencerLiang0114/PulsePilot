import struct

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pulsepilot.app import app, decode_frame


def test_png_round_trip_preserves_rgb_and_timestamp():
    rgb = np.full((48, 64, 3), [20, 80, 140], dtype=np.uint8)
    ok, png = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    assert ok
    decoded, timestamp = decode_frame(struct.pack("<d", 3.14)+png.tobytes())
    assert timestamp == 3.14 and np.array_equal(decoded, rgb)


def test_oversized_decode_is_rejected_before_allocating_image():
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\0"*8 + struct.pack(">II", 100000, 100000)
    with pytest.raises(ValueError, match="resolution"):
        decode_frame(struct.pack("<d", 0)+fake_png)


def test_origin_and_frame_consent():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as denied, client.websocket_connect(
            "/ws/measure", headers={"origin": "https://untrusted.example"}
        ):
            pass
        assert denied.value.code == 1008
        with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
            ws.send_json({"mode": "camera", "frame_consent": False})
            assert ws.receive_json()["type"] == "error"


def test_simulation_lifecycle_and_restart():
    with TestClient(app) as client:
        for _ in range(2):
            with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
                ws.send_json({"mode": "simulation", "duration": 30})
                assert ws.receive_json()["type"] == "ready"
                sample = ws.receive_json()
                assert sample["type"] == "sample" and sample["sample"]["bpm"] is None
                ws.send_json({"type": "finish"})
                result = ws.receive_json()
                assert result["type"] == "report"
                assert result["report"]["mode"] == "simulation"
                assert result["report"]["stats"]["mean_bpm"] is None


def test_failed_initialization_releases_model_slot(monkeypatch):
    import pulsepilot.app as module
    class Broken:
        def start(self): raise RuntimeError("test initialization failure")
        def close(self): pass
    monkeypatch.setattr(module, "FacePhysEstimator", Broken)
    with TestClient(app) as client:
        for _ in range(2):
            with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
                ws.send_json({"mode": "camera", "frame_consent": True})
                assert ws.receive_json()["type"] == "status"
                assert "initialization failure" in ws.receive_json()["message"]
        assert not client.get("/health").json()["busy"]
