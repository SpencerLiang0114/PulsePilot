import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from test_graph_routing import FakeProvider
from test_sensing_agent import bad

from pulsepilot import agents
from pulsepilot.app import app
from pulsepilot.orchestration.provider import MetaProvider
from pulsepilot.orchestration.telemetry import Telemetry


@pytest.mark.parametrize("mode", ["off", "observe", "assist", "adaptive"])
def test_websocket_modes_preserve_or_change_only_authorized_outputs(monkeypatch, mode):
    import pulsepilot.app as module

    monkeypatch.setenv("AGENT_MODE", mode)
    monkeypatch.setattr(agents, "configured", lambda: True)
    monkeypatch.setattr(module, "simulated_sample", lambda t, gate: bad(t))
    records, proposed = [], []
    fake = FakeProvider()

    async def propose(self, event):
        proposed.append(event)
        await asyncio.sleep(.15)
        choice = await fake.propose(event)
        # assist only offers the deterministic committed action.
        action = event.context.candidates[0].action_id if mode == "assist" else "motion"
        return choice.model_copy(update={"action_id": action, "issue_id": action})

    async def analyze(self, event):
        await asyncio.sleep(.05)
        return await fake.analyze(event)

    monkeypatch.setattr(MetaProvider, "propose", propose)
    monkeypatch.setattr(MetaProvider, "analyze", analyze)
    record = Telemetry.record

    def captured(self, outcome):
        records.append(outcome)
        record(self, outcome)

    monkeypatch.setattr(Telemetry, "record", captured)
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        ws.send_json({"mode": "simulation", "duration": 30, "coaching": "meta", "ai_consent": True})
        ready = ws.receive_json()
        assert ready["agent_mode"] == mode
        samples, reports = [], []
        while True:
            message = ws.receive_json()
            if message["type"] == "sample":
                samples.append(message)
                if message["sample"]["t"] >= 8:
                    ws.send_json({"type": "finish"})
            elif message["type"] == "report":
                reports.append(message["report"])
                if mode in ("off", "observe") or len(reports) == 2:
                    break
        item = reports[0]["interventions"][0]
        assert item["action_id"] == ("motion" if mode == "adaptive" else "dark")
        assert item["decision_source"] == ("muse" if mode == "adaptive" else "rules")
        assert item["explanation_source"] == ("muse" if mode in ("assist", "adaptive") else "rules")
        if mode in ("assist", "adaptive"):
            assert reports[0]["ai_status"] == "pending" and reports[0]["analyst"] == "deterministic"
            assert reports[1]["analyst"] == "muse"
            assert reports[1]["stats"] == reports[0]["stats"]
            assert reports[1]["samples"] == reports[0]["samples"]
            assert reports[1]["interventions"] == reports[0]["interventions"]
            assert item["agent_event_id"] and item["graph_version"]
        else:
            assert reports[0]["analyst"] == "deterministic"
        if mode == "adaptive":
            assert sum(s["coaching_state"] == "DECIDING" for s in samples) >= 2
        else:
            assert all(s["coaching_state"] != "DECIDING" for s in samples)
        assert bool(proposed) == (mode != "off")
        assert bool(records) == (mode != "off")


def test_disconnect_during_report_cancels_model_and_releases_capacity(monkeypatch):
    from pulsepilot.app import model_lock

    started, cancelled = threading.Event(), threading.Event()
    monkeypatch.setattr(agents, "configured", lambda: True)

    async def slow(self, event):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    monkeypatch.setattr(MetaProvider, "analyze", slow)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
            ws.send_json({"mode": "simulation", "coaching": "passive", "ai_consent": True})
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"type": "finish"})
            assert ws.receive_json()["report"]["ai_status"] == "pending"
            assert started.wait(2)
        assert cancelled.wait(2)
        assert not model_lock.locked()
        with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
            ws.send_json({"mode": "simulation", "ai_consent": False})
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"type": "finish"})
            assert ws.receive_json()["report"]["ai_status"] == "not_requested"


def test_camera_frames_and_acks_continue_while_agent_is_pending(monkeypatch):
    from test_protocol import frame_packet

    import pulsepilot.app as module

    started, cancelled = threading.Event(), threading.Event()
    monkeypatch.setenv("AGENT_MODE", "adaptive")
    monkeypatch.setattr(agents, "configured", lambda: True)

    class Estimator:
        start_time = None
        camera = bad(0).camera

        def start(self): pass

        def push(self, rgb, timestamp):
            if self.start_time is None:
                self.start_time = timestamp
            self.t = timestamp-self.start_time

        def snapshot(self): return bad(self.t)

        def heatmap(self): return None

        def close(self): pass

    async def slow(self, event):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    monkeypatch.setattr(module, "FacePhysEstimator", Estimator)
    monkeypatch.setattr(MetaProvider, "propose", slow)
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        ws.send_json({"mode": "camera", "frame_consent": True, "ai_consent": True})
        assert ws.receive_json()["type"] == "status"
        assert ws.receive_json()["type"] == "ready"
        acknowledgements = 0
        for i in range(16):
            ws.send_bytes(frame_packet(i*.5))
            while True:
                message = ws.receive_json()
                if message["type"] == "ack":
                    acknowledgements += 1
                    break
        assert started.wait(2)
        assert acknowledgements == 16 and not cancelled.is_set()
        ws.send_json({"type": "finish"})
        assert ws.receive_json()["report"]["interventions"] == []
        assert cancelled.wait(2)
        assert not client.get("/health").json()["busy"]
