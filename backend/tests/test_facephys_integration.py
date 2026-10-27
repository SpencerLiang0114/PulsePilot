"""Opt-in real checkpoint/PNG/WebSocket check; generated frames do not validate accuracy."""
import os
import struct
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pulsepilot.app import app
from pulsepilot.estimator import FacePhysEstimator
from pulsepilot.schemas import CameraMetrics

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_FACEPHYS_INTEGRATION") != "1",
    reason="Set RUN_FACEPHYS_INTEGRATION=1 after fetching the FacePhys checkpoint.",
)


def test_heatmap_reads_real_checkpoint_temporal_state():
    estimator = FacePhysEstimator()
    estimator.start()
    try:
        state = estimator.model.state
        yy, xx = np.mgrid[:36, :36]
        for i in range(60):
            pattern = 120 + 25*np.sin(xx/5+i/10)*np.cos(yy/7)
            frame = np.repeat(pattern[None, ..., None], 3, axis=-1).astype(np.uint8)
            output, state = estimator.model.call(frame, state)
            assert np.isfinite(np.asarray(output["bvp"])).all()
        # Exercise actual checkpoint features without pretending synthetic input is a detected face.
        extractor = FacePhysEstimator()
        extractor.model = SimpleNamespace(state=state, box=np.array([[30, 210], [70, 250]]), n_signal=1, ts=[2.0])
        extractor.start_time = extractor.visible_since = 0
        extractor.last_timestamp = 2.0
        extractor.frame_size = (240, 320)
        extractor.camera = CameraMetrics(face_visible=True, face_count=1, confidence=.99)
        heatmap = extractor.heatmap()
        assert heatmap is not None and len(set(heatmap.values)) > 10
        assert len(heatmap.values) == 1296
    finally:
        estimator.close()


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
                        if message["type"] == "face_heatmap":
                            assert message["heatmap"] is None
                            continue
                        assert message["type"] == "sample", message
                        samples.append(message["sample"])
                ws.send_json({"type": "finish"})
                message = ws.receive_json()
                assert message["type"] == "report", message
                report = message["report"]
                assert report["mode"] == mode
                assert report["samples"] == [dict(sample, waveform=[], waveform_times=[]) for sample in samples]
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
