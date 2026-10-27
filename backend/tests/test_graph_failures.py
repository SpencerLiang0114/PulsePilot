import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from test_graph_routing import FakeProvider
from test_graph_state import coach_event, report_event

from pulsepilot.orchestration import service as module
from pulsepilot.orchestration.service import OrchestrationService


def service(event, **kwargs):
    return OrchestrationService(session_id=event.session_id, ai_consent=True, provider=FakeProvider(), **kwargs)


async def test_duplicates_and_cross_session_results_are_discarded():
    event = coach_event()
    runner = service(event)
    results = await asyncio.gather(runner.run_coach_event(event), runner.run_coach_event(event))
    assert sorted(r.route for r in results) == ["accepted", "discarded"]
    assert (await runner.run_coach_event(coach_event())).status == "inactive_session"
    assert len(runner.telemetry.records) == 1
    await runner.close()


async def test_expired_and_future_events_do_not_call_graph():
    for issued_at in (time.monotonic()-2, time.monotonic()+100):
        event = coach_event(issued_at=issued_at)
        runner = service(event)
        assert (await runner.run_coach_event(event)).status == "stale_event"
        assert runner._graphs is None


async def test_deadline_cancels_provider_and_uses_deterministic_fallback(monkeypatch):
    monkeypatch.setattr(module, "COACH_DEADLINE", .03)
    started, cancelled = asyncio.Event(), asyncio.Event()

    class Slow(FakeProvider):
        async def propose(self, event):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

    event = coach_event()
    runner = OrchestrationService(session_id=event.session_id, ai_consent=True, provider=Slow())
    start = time.monotonic()
    result = await runner.run_coach_event(event)
    assert started.is_set() and cancelled.is_set()
    assert result.status == "timeout" and result.action.action_id == "dark"
    assert result.action.source == "rules" and time.monotonic()-start < .5
    assert runner._running == {}


@pytest.mark.parametrize("terminal", ["finish_measurement", "close"])
async def test_terminal_session_paths_cancel_and_drain_tasks(terminal):
    started, cancelled = asyncio.Event(), asyncio.Event()

    class Slow(FakeProvider):
        async def propose(self, event):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

    event = coach_event()
    runner = OrchestrationService(session_id=event.session_id, ai_consent=True, provider=Slow())
    task = asyncio.create_task(runner.run_coach_event(event))
    await started.wait()
    await getattr(runner, terminal)()
    assert task.cancelled() and cancelled.is_set() and runner._running == {}
    assert (await runner.run_coach_event(coach_event(session_id=event.session_id))).route == "discarded"
    assert not runner.telemetry.records


async def test_off_never_constructs_or_executes_graph():
    for event in (coach_event(), report_event()):
        runner = service(event, mode="off")
        result = await (runner.run_coach_event(event) if event.event_type == "coach_request"
                        else runner.run_report_event(event))
        assert result.route == "disabled" and runner._graphs is None
        assert not runner.telemetry.records


async def test_session_consent_cannot_be_escalated_by_event():
    event = coach_event(ai_consent=True)
    provider = FakeProvider()
    provider.propose = AsyncMock(side_effect=AssertionError("unauthorized call"))
    runner = OrchestrationService(session_id=event.session_id, ai_consent=False, provider=provider)
    assert (await runner.run_coach_event(event)).status == "not_requested"
    provider.propose.assert_not_called()


async def test_report_cancellation_is_propagated():
    started = asyncio.Event()

    class Slow(FakeProvider):
        async def analyze(self, event):
            started.set()
            await asyncio.Future()

    event = report_event()
    runner = OrchestrationService(session_id=event.session_id, provider=Slow(), ai_consent=True)
    task = asyncio.create_task(runner.run_report_event(event))
    await started.wait()
    await runner.close()
    assert task.cancelled() and not runner.telemetry.records


async def test_telemetry_contains_only_safe_metadata(caplog):
    event = coach_event()
    with caplog.at_level("INFO", logger="pulsepilot.agents"):
        await service(event).run_coach_event(event)
    for forbidden in ("brightness", "sqi", "waveform", "context", "explanation", "MODEL_API_KEY"):
        assert forbidden not in caplog.text
    assert event.event_id in caplog.text and "graph_latency_ms" in caplog.text
