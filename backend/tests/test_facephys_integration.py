"""Opt-in real checkpoint/PNG/WebSocket check; generated frames do not validate accuracy."""
import os
import struct
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pulsepilot.app import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_FACEPHYS_INTEGRATION") != "1",
    reason="Set RUN_FACEPHYS_INTEGRATION=1 after fetching the FacePhys checkpoint.",
)


def test_real_checkpoint_stream_finish_and_fresh_recording_session():
    ok, png = cv2.imencode(".png", np.full((240, 320, 3), 120, dtype=np.uint8))
    assert ok
    with TestClient(app) as client:
        assert client.get("/health").json()["weights_available"]
        for mode, frames in [("camera", 330), ("recording", 3)]:
            with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
                ws.send_json({"mode": mode, "frame_consent": True, "ai_consent": False})
                assert ws.receive_json()["type"] == "status"
                assert ws.receive_json()["type"] == "ready"
                samples = []
                began = time.monotonic()
                for index in range(frames):
                    timestamp = index/30
                    time.sleep(max(0, began+timestamp-time.monotonic()))
                    ws.send_bytes(struct.pack("<d", timestamp)+png.tobytes())
                    while True:
                        message = ws.receive_json()
                        if message["type"] == "ack":
                            break
                        assert message["type"] == "sample", message
                        samples.append(message["sample"])
                ws.send_json({"type": "finish"})
                message = ws.receive_json()
                assert message["type"] == "report", message
                report = message["report"]
                assert report["mode"] == mode
                assert report["samples"] == [dict(sample, waveform=[]) for sample in samples]
                assert samples[0]["t"] == 0
                assert all(sample["bpm"] is None and not sample["usable"] for sample in samples)
                assert all(not sample["camera"]["face_visible"] for sample in samples)
                assert report["stats"]["mean_bpm"] is None
                if mode == "camera":
                    assert samples[-1]["t"] >= 10
                    assert samples[-1]["fps"] == 30
                with pytest.raises(WebSocketDisconnect):
                    ws.receive_json()
            health = client.get("/health").json()
            assert health["model_ready"] and not health["busy"] and health["model_error"] is None
