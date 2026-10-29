import asyncio
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from test_health_insights import native_report

from pulsepilot.health_guidance import HealthGuidanceCatalog
from pulsepilot.orchestration.contracts import HealthInsightProposal, HealthInsightReference
from pulsepilot.orchestration.provider import MetaProvider
from pulsepilot.orchestration.service import OrchestrationService
from pulsepilot.orchestration.validation import validate_health_insights


class HealthProvider:
    identifier = "fixture"

    def __init__(self):
        self.calls = 0

    async def health_insights(self, event):
        self.calls += 1
        candidates = HealthGuidanceCatalog.candidates(event.evidence)[:3]
        return HealthInsightProposal(session_id=event.session_id, event_id=event.event_id,
            report_id=event.evidence.report_id, selections=[HealthInsightReference(guidance_id=c.insight_id,
                evidence_ids=c.evidence_ids, guidance_reference_ids=c.guidance_reference_ids) for c in candidates])


@pytest.mark.parametrize("mode", ["off", "observe", "assist", "adaptive"])
@pytest.mark.parametrize("consent", [False, True])
async def test_health_consent_and_agent_modes_are_independent_of_coaching(mode, consent):
    provider = HealthProvider()
    service = OrchestrationService(mode=mode, ai_consent=True, health_ai_consent=consent, provider=provider)
    event = service.health_insight_event(native_report())
    result = await service.run_health_insight_event(event)
    assert provider.calls == int(consent and mode != "off")
    assert result.health_insights.analyst == ("muse" if consent and mode in ("assist", "adaptive") else "deterministic")
    assert result.health_insights.report_id == event.evidence.report_id
    assert result.graph_version == "p3.1"
    assert all("health_insights" not in r for r in service.telemetry.records)
    await service.close()


async def test_health_opt_in_works_without_p2_consent():
    provider = HealthProvider()
    service = OrchestrationService(ai_consent=False, health_ai_consent=True, provider=provider)
    report = native_report()
    event = service.health_insight_event(report)
    report.stats.mean_bpm = 170.0
    outcome = await service.run_health_insight_event(event)
    assert outcome.route == "accepted" and "72" in outcome.health_insights.insights[0].text
    assert provider.calls == 1


@pytest.mark.parametrize("mutation", ["session", "event", "report", "invented", "duplicate", "evidence", "guidance_ref", "missing", "prose"])
async def test_invalid_proposals_cannot_reach_display(mutation):
    provider = HealthProvider()
    service = OrchestrationService(health_ai_consent=True, provider=provider)
    event = service.health_insight_event(native_report())
    good = await provider.health_insights(event)
    data = good.model_dump()
    if mutation in ("session", "event", "report"):
        data[mutation + "_id"] = str(uuid4())
    elif mutation == "invented":
        data["selections"][0]["guidance_id"] = "diagnose_arrhythmia"
    elif mutation == "duplicate":
        data["selections"][1] = data["selections"][0]
    elif mutation == "evidence":
        data["selections"][0]["evidence_ids"] = ["context"]
    elif mutation == "guidance_ref":
        data["selections"][0]["guidance_reference_ids"] = ["invented_trial"]
    elif mutation == "missing":
        data["selections"] = data["selections"][1:]
    else:
        data["text"] = "You are healthy; stop your medication."
    if mutation == "prose":
        with pytest.raises(ValidationError):
            HealthInsightProposal.model_validate(data)
    else:
        bad = HealthInsightProposal.model_validate(data)
        assert not validate_health_insights(event, bad).valid
        async def invalid(_): return bad
        provider.health_insights = invalid
        outcome = await service.run_health_insight_event(event)
        assert outcome.route == "fallback" and outcome.health_insights.analyst == "deterministic"


async def test_model_cannot_suppress_symptom_guidance():
    provider = HealthProvider()
    service = OrchestrationService(health_ai_consent=True, provider=provider)
    event = service.health_insight_event(native_report(symptoms=True))
    proposal = await provider.health_insights(event)
    assert not validate_health_insights(event, proposal.model_copy(update={"selections": proposal.selections[1:]})).valid
    reversed_proposal = proposal.model_copy(update={"selections": list(reversed(proposal.selections))})
    async def reversed_selection(_): return reversed_proposal
    provider.health_insights = reversed_selection
    result = await service.run_health_insight_event(event)
    assert result.health_insights.insights[0].insight_id == "urgent"


@pytest.mark.parametrize("error", [RuntimeError("offline"), ValueError("invalid"), httpx.ReadTimeout("slow")])
async def test_provider_failures_preserve_deterministic_guidance(error):
    provider = HealthProvider()
    async def fail(_): raise error
    provider.health_insights = fail
    service = OrchestrationService(health_ai_consent=True, provider=provider)
    result = await service.run_health_insight_event(service.health_insight_event(native_report()))
    assert result.health_insights.status == "fallback"
    assert result.health_insights.insights[0].insight_id == "estimate"


async def test_deadline_cancellation_and_finish_independence(monkeypatch):
    import pulsepilot.orchestration.service as module
    monkeypatch.setattr(module, "HEALTH_DEADLINE", .04)
    provider = HealthProvider()
    started, cancelled = asyncio.Event(), asyncio.Event()
    async def slow(_):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
    provider.health_insights = slow
    service = OrchestrationService(health_ai_consent=True, provider=provider)
    task = asyncio.create_task(service.run_health_insight_event(service.health_insight_event(native_report())))
    await started.wait()
    await service.finish_measurement()
    assert not task.done()
    assert (await task).status == "timeout"
    assert cancelled.is_set()
    monkeypatch.setattr(module, "HEALTH_DEADLINE", 12.0)
    started.clear(); cancelled.clear()
    task = asyncio.create_task(service.run_health_insight_event(service.health_insight_event(native_report())))
    await started.wait()
    await service.close()
    assert task.cancelled() and cancelled.is_set() and not service._running


async def test_stale_duplicate_cross_session_and_parallel_results():
    provider = HealthProvider()
    a = OrchestrationService(health_ai_consent=True, provider=provider)
    b = OrchestrationService(health_ai_consent=True, provider=provider)
    event = a.health_insight_event(native_report())
    assert (await b.run_health_insight_event(event)).route == "discarded"
    stale = a.health_insight_event(native_report()).model_copy(update={"issued_at": 0.0})
    assert (await a.run_health_insight_event(stale)).route == "discarded"
    results = await asyncio.gather(a.run_health_insight_event(event), b.run_health_insight_event(b.health_insight_event(native_report())))
    assert all(r.route == "accepted" for r in results)
    assert results[0].health_insights.report_id != results[1].health_insights.report_id
    assert (await a.run_health_insight_event(event)).route == "discarded"
    assert provider.calls == 2


async def test_provider_payload_uses_only_structured_health_evidence(monkeypatch):
    captured = {}
    async def generate(self, schema, event, payload, instruction):
        captured.update(payload)
        return await HealthProvider().health_insights(event)
    monkeypatch.setattr(MetaProvider, "_generate", generate)
    service = OrchestrationService(health_ai_consent=True)
    await service.run_health_insight_event(service.health_insight_event(native_report()))
    assert set(captured) == {"session_id", "event_id", "report_id", "evidence", "eligible_guidance"}
    assert "samples" not in captured["evidence"] and "images" not in captured["evidence"]
    await service.close()
