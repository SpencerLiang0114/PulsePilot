import asyncio
import struct
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pulsepilot.app import app, decode_frame


def frame_packet(timestamp=0):
    ok, png = cv2.imencode(".png", np.full((48, 64, 3), 120, dtype=np.uint8))
    assert ok
    return struct.pack("<d", timestamp) + png.tobytes()


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf"), -1])
def test_invalid_timestamps_are_rejected_before_image_decode(monkeypatch, timestamp):
    packet = frame_packet(timestamp)
    monkeypatch.setattr(cv2, "imdecode", lambda *args: pytest.fail("Invalid timestamp reached the decoder"))
    with pytest.raises(ValueError, match="timestamp"):
        decode_frame(packet)


@pytest.mark.parametrize("command", [[], None, {"type": "finish", "extra": True}])
def test_invalid_commands_have_protocol_errors(command):
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        ws.send_json({"mode": "simulation"})
        assert ws.receive_json()["type"] == "ready"
        ws.send_json(command)
        error = ws.receive_json()
        assert error["type"] == "error"
        assert "command" in error["message"].lower()


async def test_cancellation_waits_for_inference_before_cleanup():
    import pulsepilot.app as module

    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    def work():
        started.set()
        release.wait(5)
        finished.set()

    task = asyncio.create_task(module.run_inference(work))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(.01)
        assert not task.done(), "Cleanup could race with the inference thread"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()
    finally:
        release.set()


def test_png_round_trip_preserves_rgb_and_timestamp():
    rgb = np.full((48, 64, 3), [20, 80, 140], dtype=np.uint8)
    ok, png = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    assert ok
    decoded, timestamp = decode_frame(struct.pack("<d", 3.14)+png.tobytes())
    assert timestamp == 3.14 and np.array_equal(decoded, rgb)


def test_oversized_decode_is_rejected_before_allocating_image():
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" + struct.pack(">II", 100000, 100000) + b"\0"*9
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


@pytest.fixture
def estimators(monkeypatch):
    import pulsepilot.app as module
    from pulsepilot.schemas import Sample

    instances = []

    class Estimator:
        from pulsepilot.schemas import CameraMetrics
        camera = CameraMetrics()

        def __init__(self):
            self.start_time = None
            self.last_timestamp = None
            self.closed = 0
            instances.append(self)

        def start(self):
            pass

        def push(self, rgb, timestamp):
            assert rgb.dtype == np.uint8 and rgb.shape == (48, 64, 3)
            if self.last_timestamp is not None and timestamp <= self.last_timestamp:
                raise ValueError("Capture timestamps must increase.")
            if self.start_time is None:
                self.start_time = timestamp
            self.last_timestamp = timestamp

        def snapshot(self):
            return Sample(t=self.last_timestamp-self.start_time)

        def heatmap(self):
            return None

        def close(self):
            self.closed += 1

    monkeypatch.setattr(module, "FacePhysEstimator", Estimator)
    monkeypatch.setattr(module, "model_status", {"ready": False, "error": None})
    return instances


def start_camera(ws):
    ws.send_json({"mode": "camera", "frame_consent": True, "ai_consent": False})
    assert ws.receive_json()["type"] == "status"
    assert ws.receive_json()["type"] == "ready"


def test_camera_stream_busy_finish_and_restart(estimators):
    with TestClient(app) as client:
        for _ in range(2):
            with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
                start_camera(ws)
                assert client.get("/health").json()["busy"]
                with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as busy:
                    busy.send_json({"mode": "camera", "frame_consent": True})
                    assert "another session" in busy.receive_json()["message"]
                for timestamp in [10, 10.5, 11]:
                    ws.send_bytes(frame_packet(timestamp))
                    assert ws.receive_json()["heatmap"] is None
                    sample = ws.receive_json()
                    assert sample["type"] == "sample"
                    assert sample["sample"]["t"] == timestamp-10
                    assert ws.receive_json()["type"] == "ack"
                ws.send_json({"type": "finish"})
                report = ws.receive_json()["report"]
                assert len(report["samples"]) == 3
                assert report["stats"]["mean_bpm"] is None
                assert not client.get("/health").json()["busy"]
        assert len(estimators) == 2
        assert all(estimator.closed == 1 for estimator in estimators)


@pytest.mark.parametrize("capture_fps", [15, 30, 60, 120])
def test_heatmap_stream_targets_60hz_without_changing_sample_rate(estimators, capture_fps):
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        start_camera(ws)
        heatmaps, samples = 0, 0
        for index in range(2*capture_fps):
            ws.send_bytes(frame_packet(10 + index/capture_fps))
            while True:
                message = ws.receive_json()
                if message["type"] == "ack":
                    break
                if message["type"] == "face_heatmap":
                    assert message["t"] == pytest.approx(index/capture_fps)
                    assert "camera" in message
                    heatmaps += 1
                elif message["type"] == "sample":
                    samples += 1
                else:
                    pytest.fail(f"Unexpected message: {message['type']}")
        assert heatmaps == 2*min(capture_fps, 60)
        assert samples == (5 if capture_fps == 120 else 4)
        ws.send_json({"type": "finish"})
        assert ws.receive_json()["type"] == "report"


def test_heatmap_stream_is_transient_and_absent_from_reports(monkeypatch, estimators):
    import pulsepilot.app as module
    from pulsepilot.schemas import FaceHeatmap

    heatmap = FaceHeatmap(t=0, bbox=[.2, .1, .8, .9], values=[128]*1296)
    monkeypatch.setattr(module.FacePhysEstimator, "heatmap", lambda self: heatmap)
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        start_camera(ws)
        ws.send_bytes(frame_packet())
        assert ws.receive_json()["heatmap"] == heatmap.model_dump()
        assert ws.receive_json()["type"] == "sample"
        assert ws.receive_json()["type"] == "ack"
        ws.send_json({"type": "finish"})
        report = ws.receive_json()["report"]
        assert len(report["samples"]) == 1
        assert "heatmap" not in str(report)


@pytest.mark.parametrize("terminal", ["disconnect", "idle", "invalid_frame", "duplicate", "duration"])
def test_camera_terminal_paths_release_capacity(monkeypatch, estimators, terminal):
    import pulsepilot.app as module

    if terminal == "idle":
        monkeypatch.setattr(module, "FRAME_TIMEOUT", .02)
    if terminal == "duration":
        monkeypatch.setattr(module, "SESSION_TIMEOUT", 0)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
            start_camera(ws)
            if terminal == "invalid_frame":
                ws.send_bytes(b"not a frame")
            elif terminal == "duplicate":
                ws.send_bytes(frame_packet())
                assert ws.receive_json()["type"] == "face_heatmap"
                assert ws.receive_json()["type"] == "sample"
                assert ws.receive_json()["type"] == "ack"
                ws.send_bytes(frame_packet())
            if terminal != "disconnect":
                assert ws.receive_json()["type"] == ("report" if terminal == "duration" else "error")
                with pytest.raises(WebSocketDisconnect):
                    ws.receive_json()
        assert not client.get("/health").json()["busy"]
        assert estimators[0].closed == 1
        with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
            start_camera(ws)
            if terminal != "duration":
                ws.send_json({"type": "finish"})
            assert ws.receive_json()["type"] == "report"


def test_failed_restart_clears_readiness_and_can_recover(monkeypatch, estimators):
    import pulsepilot.app as module

    original_start = module.FacePhysEstimator.start
    with TestClient(app) as client:
        for fail in [False, True, False]:
            def start(self, fail=fail):
                if fail:
                    raise RuntimeError("Model startup failed")
                original_start(self)

            monkeypatch.setattr(module.FacePhysEstimator, "start", start)
            with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
                ws.send_json({"mode": "camera", "frame_consent": True})
                assert ws.receive_json()["type"] == "status"
                assert ws.receive_json()["type"] == ("error" if fail else "ready")
                if not fail:
                    ws.send_json({"type": "finish"})
                    assert ws.receive_json()["type"] == "report"
                with pytest.raises(WebSocketDisconnect):
                    ws.receive_json()
            health = client.get("/health").json()
            assert health["model_ready"] is not fail
            assert bool(health["model_error"]) is fail
            assert not health["busy"]


async def test_cancel_during_initialization_keeps_slot_until_workers_stop(monkeypatch, estimators):
    import pulsepilot.app as module

    started, release = threading.Event(), threading.Event()

    def start(self):
        started.set()
        release.wait(5)

    monkeypatch.setattr(module.FacePhysEstimator, "start", start)
    ws = SimpleNamespace(
        headers={"origin": "http://localhost:3000"}, accept=AsyncMock(), close=AsyncMock(),
        receive_json=AsyncMock(return_value={"mode": "camera", "frame_consent": True}), send_json=AsyncMock(),
    )
    task = asyncio.create_task(module.measurement(ws))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(.01)
        assert module.model_lock.locked() and estimators[0].closed == 0
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert estimators[0].closed == 1
        assert not module.model_lock.locked()
        ws.close.assert_awaited_once()
    finally:
        release.set()
