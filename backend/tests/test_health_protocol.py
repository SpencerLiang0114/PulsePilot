import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from test_graph_health import HealthProvider
from test_graph_routing import FakeProvider

from pulsepilot import agents
from pulsepilot.app import app, model_lock
from pulsepilot.orchestration.provider import MetaProvider


@pytest.mark.parametrize("first", ["health", "analysis"])
def test_independent_delivery_keeps_report_and_evidence(monkeypatch, first):
    monkeypatch.setattr(agents, "configured", lambda: True)
    async def health(self, event):
        await asyncio.sleep(.005 if first == "health" else .04)
        return await HealthProvider().health_insights(event)
    async def analysis(self, event):
        await asyncio.sleep(.005 if first == "analysis" else .04)
        return await FakeProvider().analyze(event)
    monkeypatch.setattr(MetaProvider, "health_insights", health)
    monkeypatch.setattr(MetaProvider, "analyze", analysis)
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        ws.send_json({"mode": "simulation", "coaching": "passive", "ai_consent": True, "health_ai_consent": True})
        ready = ws.receive_json()
        ws.send_json({"type": "finish"})
        initial = ws.receive_json()["report"]
        assert initial["ai_status"] == initial["health_insights"]["status"] == "pending"
        assert initial["health_insights"]["insights"][0]["insight_id"] == "simulation"
        updates = [ws.receive_json(), ws.receive_json()]
        assert updates[0]["type"] == ("health_insight" if first == "health" else "report")
        health_message = next(m for m in updates if m["type"] == "health_insight")
        final = next(m for m in updates if m["type"] == "report")["report"]
        assert health_message["session_id"] == ready["session_id"]
        assert health_message["event_id"] == initial["health_insights"]["agent_event_id"]
        assert health_message["report_id"] == initial["id"]
        assert health_message["health_insights"]["analyst"] == "muse"
        for key in ("stats", "samples", "interventions", "evidence"):
            assert final[key] == initial[key]
        assert not model_lock.locked()


def test_no_health_opt_in_never_calls_health_provider(monkeypatch):
    monkeypatch.setattr(agents, "configured", lambda: True)
    async def forbidden(*args): pytest.fail("Health data transferred without consent")
    async def analysis(self, event): return await FakeProvider().analyze(event)
    monkeypatch.setattr(MetaProvider, "health_insights", forbidden)
    monkeypatch.setattr(MetaProvider, "analyze", analysis)
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        ws.send_json({"mode": "simulation", "ai_consent": True, "coaching": "passive"})
        ws.receive_json()
        ws.send_json({"type": "finish"})
        assert ws.receive_json()["report"]["health_insights"]["status"] == "not_requested"
        assert ws.receive_json()["report"]["analyst"] == "muse"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_health_failure_preserves_numerical_report_and_p2(monkeypatch):
    monkeypatch.setattr(agents, "configured", lambda: True)
    async def fail(self, event): raise RuntimeError("offline")
    async def analysis(self, event): return await FakeProvider().analyze(event)
    monkeypatch.setattr(MetaProvider, "health_insights", fail)
    monkeypatch.setattr(MetaProvider, "analyze", analysis)
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        ws.send_json({"mode": "simulation", "ai_consent": True, "health_ai_consent": True, "coaching": "passive"})
        ws.receive_json(); ws.send_json({"type": "finish"})
        initial = ws.receive_json()["report"]
        messages = [ws.receive_json(), ws.receive_json()]
        bundle = next(m["health_insights"] for m in messages if m["type"] == "health_insight")
        report = next(m["report"] for m in messages if m["type"] == "report")
        assert bundle["status"] == "fallback" and bundle["analyst"] == "deterministic"
        assert bundle["insights"] == initial["health_insights"]["insights"]
        assert report["stats"] == initial["stats"] and report["analyst"] == "muse"


def test_disconnect_cancels_both_graphs_and_reconnect_has_new_identity(monkeypatch):
    monkeypatch.setattr(agents, "configured", lambda: True)
    starts = [threading.Event(), threading.Event()]
    cancels = [threading.Event(), threading.Event()]
    async def slow(index):
        starts[index].set()
        try: await asyncio.Future()
        finally: cancels[index].set()
    async def health(self, event): await slow(0)
    async def analysis(self, event): await slow(1)
    monkeypatch.setattr(MetaProvider, "health_insights", health)
    monkeypatch.setattr(MetaProvider, "analyze", analysis)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
            ws.send_json({"mode": "simulation", "ai_consent": True, "health_ai_consent": True, "coaching": "passive"})
            old = ws.receive_json()["session_id"]
            ws.send_json({"type": "finish"})
            assert ws.receive_json()["type"] == "report"
            assert all(e.wait(2) for e in starts)
        assert all(e.wait(2) for e in cancels)
        with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
            ws.send_json({"mode": "simulation"})
            assert ws.receive_json()["session_id"] != old
            ws.send_json({"type": "finish"})
            assert ws.receive_json()["report"]["health_insights"]["status"] == "not_requested"
