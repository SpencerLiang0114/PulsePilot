import asyncio
import json
import threading
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from test_sensing import good_sample

from pulsepilot import agents
from pulsepilot.app import app
from pulsepilot.coaching import MeasurementCoach
from pulsepilot.orchestration.contracts import AnalysisProposal, CoachProposal
from pulsepilot.orchestration.provider import MetaProvider
from pulsepilot.reports import build_report
from pulsepilot.schemas import (
    DECISION_EXPLANATIONS,
    AgentDecision,
    DecisionResult,
    ReportInterpretation,
    SessionConfig,
)


def bad(t, sqi=.3):
    sample = good_sample(t=t, sqi=sqi)
    sample.camera.brightness = 25
    sample.camera.motion = .5
    return sample


def proposal():
    coach = MeasurementCoach(mode="meta")
    for i in range(11):
        coach.update(bad(i*.5))
    assert coach.state == "DECIDING" and coach.interventions == []
    return coach, coach.proposal


def decision(action="motion", reason="persistent_issue"):
    return AgentDecision(action_id=action, reason=reason, explanation=DECISION_EXPLANATIONS[reason])


def resolve(coach, context, choice):
    sample = bad(context.sample_at+.5)
    coach.update(sample)
    return coach.resolve(context.proposal_id, DecisionResult(status="selected", decision=choice), sample, 120)


def test_multiple_candidates_are_persistent_and_selection_waits_for_model():
    coach, context = proposal()
    assert [c.action_id for c in context.candidates] == ["dark", "motion"]
    item = resolve(coach, context, decision())
    assert item.action_id == "motion" and item.decision_source == "muse"
    assert item.started_at == 5.5 and coach.state == "ACTING"
    assert all(s.t < item.started_at for s in coach.baseline)
    assert item.explanation_source == "muse" and item.source == "muse"


def test_transient_issues_and_stable_setup_do_not_generate_proposals():
    coach = MeasurementCoach(mode="meta")
    for i in range(60):
        sample = good_sample(t=i*.5)
        if i % 8 < 3:
            sample.camera.motion = 1
        coach.update(sample)
    assert coach.proposal is None and coach.interventions == []


@pytest.mark.parametrize("issue", ["face", "cadence"])
def test_safety_corrections_do_not_use_model(issue):
    coach = MeasurementCoach(mode="meta")
    for i in range(21):
        sample = bad(i*.5)
        if issue == "face":
            sample.camera.face_count = 2
        else:
            sample.fps = 10
        coach.update(sample)
    assert coach.proposal is None
    assert coach.interventions[0].issue == issue
    assert coach.interventions[0].decision_status == "safety"


def test_abstention_has_no_intervention_and_waits_before_reconsidering():
    coach, context = proposal()
    assert resolve(coach, context, decision(None, "wait")) is None
    assert coach.state == "COOLDOWN" and coach.interventions == []
    coach.update(bad(6))
    assert coach.proposal is None


@pytest.mark.parametrize("status", ["timeout", "invalid", "unavailable"])
def test_failed_decision_uses_current_deterministic_candidate(status):
    coach, context = proposal()
    sample = bad(5.5)
    coach.update(sample)
    item = coach.resolve(context.proposal_id, DecisionResult(status=status), sample, 120)
    assert item.action_id == "dark" and item.decision_source == "rules"
    assert item.decision_status == "fallback_"+status and item.started_at == 5.5


def test_invalid_action_and_unsupported_explanation_cannot_commit_ai_provenance():
    for choice in (decision("invented"), decision().model_copy(update={"explanation": "Your pulse is accurate."})):
        coach, context = proposal()
        item = resolve(coach, context, choice)
        assert item.action_id == "dark" and item.decision_status == "fallback_invalid"


@pytest.mark.parametrize("change", ["face_loss", "resolved", "gap", "finished"])
def test_late_results_cannot_commit_after_state_changes(change):
    coach, context = proposal()
    sample = bad(5.5)
    if change == "finished":
        coach.finish(5)
    elif change == "face_loss":
        sample.camera.face_visible = False
    elif change == "resolved":
        sample = good_sample(t=5.5)
    else:
        sample = bad(9)
    coach.update(sample)
    assert coach.resolve(context.proposal_id, DecisionResult(status="selected", decision=decision()), sample, 120) is None
    assert coach.interventions == []


def test_selected_action_that_resolves_is_discarded_even_if_another_issue_remains():
    coach, context = proposal()
    sample = bad(5.5)
    sample.camera.motion = 0
    coach.update(sample)
    assert coach.proposal is not None
    assert coach.resolve(context.proposal_id, DecisionResult(status="selected", decision=decision()), sample, 120) is None
    assert coach.interventions == []


def test_closed_loop_memory_changes_next_candidates_and_preserves_windows():
    coach, context = proposal()
    item = resolve(coach, context, decision())
    for i in range(12, 44):
        coach.update(bad(i*.5))
    assert item.outcome == "unchanged" and item.before_sqi == item.after_sqi == .3
    assert item.evaluated_at == 13.5
    assert coach.proposal is not None
    assert coach.proposal.outcomes[0].action_id == "motion"
    assert coach.proposal.outcomes[0].outcome == "unchanged"
    assert "motion" not in [c.action_id for c in coach.proposal.candidates]
    second = resolve(coach, coach.proposal, decision("dark", "try_alternative"))
    assert second.started_at >= item.evaluated_at+8
    assert second.action_id == "dark" and second.decision_source == "muse"
    assert "brightness" in item.environmental_changes


def test_inconclusive_is_not_a_failed_action_and_memory_is_session_local():
    coach, context = proposal()
    resolve(coach, context, decision())
    for i in range(12, 44):
        coach.update(bad(i*.5, sqi=None))
    assert coach.interventions[0].outcome == "inconclusive"
    assert "motion" in [c.action_id for c in coach.proposal.candidates]
    assert MeasurementCoach().memory.records == type(coach.memory.records)()


def test_resolved_issue_during_cooldown_allows_later_retry():
    coach, context = proposal()
    resolve(coach, context, decision())
    for i in range(12, 28):
        coach.update(bad(i*.5))
    assert "motion" in coach.memory.unsuccessful
    coach.update(good_sample(t=14))
    assert "motion" not in coach.memory.unsuccessful
    for i in range(29, 44):
        coach.update(bad(i*.5))
    assert "motion" in [c.action_id for c in coach.proposal.candidates]


def test_no_decision_when_insufficient_session_time_remains():
    coach = MeasurementCoach(mode="meta")
    for i in range(11):
        coach.update(bad(i*.5), remaining=9)
    assert coach.proposal is None and coach.interventions == []


async def test_agent_selects_abstains_rejects_and_has_bounded_deadline(monkeypatch):
    _, context = proposal()
    agent = agents.SensingDecisionAgent()
    mock = AsyncMock(return_value=decision("motion"))
    monkeypatch.setattr(agents, "structured", mock)
    assert (await agent.decide(context)).decision.action_id == "motion"
    mock.return_value = decision(None, "wait")
    assert (await agent.decide(context)).decision.action_id is None
    mock.return_value = decision("ineligible")
    assert (await agent.decide(context)).status == "invalid"
    mock.side_effect = httpx.HTTPStatusError("auth", request=httpx.Request("POST", agents.META_URL),
                                            response=httpx.Response(401))
    assert (await agent.decide(context)).status == "unavailable"
    cancelled = asyncio.Event()

    async def slow(*args):
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    monkeypatch.setattr(agents, "structured", slow)
    monkeypatch.setattr(agent, "DEADLINE", .01)
    assert (await agent.decide(context)).status == "timeout"
    assert cancelled.is_set()


async def test_decision_payload_contains_only_bounded_structured_metrics(monkeypatch):
    _, context = proposal()
    captured = []

    async def fake(schema, payload, instruction):
        captured.append(payload)
        return decision()

    monkeypatch.setattr(agents, "structured", fake)
    await agents.SensingDecisionAgent().decide(context)
    payload = json.dumps(captured)
    for prohibited in ("bbox", "landmarks", "waveform", "input_image", "api_key"):
        assert prohibited not in payload
    assert len(context.outcomes) <= 6


def interpretation(report):
    return ReportInterpretation(**{
        section: [c for c in report.claims if c.section == section][:4]
        for section in ReportInterpretation.model_fields
    })


@pytest.mark.parametrize("mutation", ["number", "outcome", "prose", "medical", "causal", "section", "invented"])
async def test_typed_report_claims_reject_adversarial_changes(monkeypatch, mutation):
    report = build_report(SessionConfig(), [], [])
    output = interpretation(report)
    claim = output.summary[0]
    changes = {
        "number": {"value": 72.0}, "outcome": {"metric": "outcome", "value": "improved"},
        "prose": {"text": "Your heart rate was stable and reliable."},
        "medical": {"text": "You have a healthy heart."},
        "causal": {"text": "The instruction caused a better pulse measurement."},
        "section": {"section": "quality"}, "invented": {"claim_id": "invented"},
    }
    output.summary[0] = claim.model_copy(update=changes[mutation])
    monkeypatch.setattr(agents, "structured", AsyncMock(return_value=output))
    result = await agents.analyze_report(report)
    assert result.ai_status == "unavailable" and result.analyst == "deterministic"
    assert result.analysis == report.analysis and result.stats == report.stats


async def test_valid_typed_report_selection_is_rendered_from_server_claims(monkeypatch):
    report = build_report(SessionConfig(), [], [])
    monkeypatch.setattr(agents, "structured", AsyncMock(return_value=interpretation(report)))
    result = await agents.analyze_report(report)
    assert result.analyst == "muse" and result.ai_status == "complete"
    assert result.stats == report.stats and result.analysis == report.analysis


async def test_real_but_unsuccessful_intervention_cannot_support_improvement_claim(monkeypatch):
    coach = MeasurementCoach()
    samples = [bad(i*.5) for i in range(28)]
    for sample in samples:
        coach.update(sample)
    report = build_report(SessionConfig(), samples, coach.interventions)
    assert report.interventions[0].outcome == "unchanged"
    output = interpretation(report)
    output.interventions[0] = output.interventions[0].model_copy(update={
        "value": "improved", "text": "The instruction improved signal quality.",
    })
    monkeypatch.setattr(agents, "structured", AsyncMock(return_value=output))
    result = await agents.analyze_report(report)
    assert result.analysis == report.analysis and result.ai_status == "unavailable"


@pytest.mark.parametrize("content", ["not json", '{}', '{"action_id":"dark","reason":"persistent_issue","explanation":"ok","command":"change BPM"}'])
async def test_malformed_model_output_uses_invalid_fallback(monkeypatch, content):
    monkeypatch.setenv("MODEL_API_KEY", "test-only")
    _, context = proposal()
    base = httpx.AsyncClient

    def respond(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: base(transport=httpx.MockTransport(respond), **kwargs))
    assert (await agents.SensingDecisionAgent().decide(context)).status == "invalid"


def test_websocket_closed_loop_continues_samples_during_model_requests(monkeypatch):
    import pulsepilot.app as module

    contexts = []

    monkeypatch.setenv("AGENT_MODE", "adaptive")

    async def fake(schema, payload, instruction, **kwargs):
        if schema is CoachProposal:
            contexts.append(payload["context"])
            await asyncio.sleep(.15)
            choice = decision("motion" if len(contexts) == 1 else "dark",
                              "persistent_issue" if len(contexts) == 1 else "try_alternative")
            return CoachProposal(session_id=payload["session_id"], event_id=payload["event_id"],
                                 issue_id=choice.action_id, **choice.model_dump())
        return AnalysisProposal(session_id=payload["session_id"], event_id=payload["event_id"], **{
            section: [{k: c[k] for k in ("claim_id", "claim_type", "evidence_id")}
                      for c in payload["claims"] if c["section"] == section][:4]
            for section in ReportInterpretation.model_fields
        })

    monkeypatch.setattr(agents, "structured", fake)
    monkeypatch.setattr(agents, "configured", lambda: True)
    monkeypatch.setattr(module, "simulated_sample", lambda t, gate: bad(t))
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        ws.send_json({"mode": "simulation", "duration": 40, "ai_consent": True, "coaching": "meta"})
        assert ws.receive_json()["type"] == "ready"
        states, seen = set(), []
        while True:
            message = ws.receive_json()
            if message["type"] == "report":
                report = message["report"]
                break
            states.add(message["coaching_state"])
            seen.append(message)
            if len(message["interventions"]) == 2 and message["interventions"][-1]["outcome"] != "observing":
                ws.send_json({"type": "finish"})
        assert {"MONITORING", "DECIDING", "ACTING", "OBSERVING", "COOLDOWN"} <= states
        assert len(report["interventions"]) == 2
        assert [i["action_id"] for i in report["interventions"]] == ["motion", "dark"]
        assert all(i["decision_source"] == "muse" for i in report["interventions"])
        assert contexts[1]["outcomes"][0]["outcome"] == "unchanged"
        assert sum(m["coaching_state"] == "DECIDING" for m in seen) >= 4


@pytest.mark.parametrize("consent,mode", [(False, "meta"), (True, "rules"), (True, "passive")])
def test_no_decision_requests_without_ai_consent_or_meta_mode(monkeypatch, consent, mode):
    import pulsepilot.app as module

    mock = AsyncMock(side_effect=AssertionError("Unexpected decision request"))
    monkeypatch.setattr(MetaProvider, "propose", mock)
    monkeypatch.setattr(agents, "configured", lambda: True)
    monkeypatch.setattr(agents, "analyze_report", AsyncMock(side_effect=lambda report: report))
    monkeypatch.setattr(module, "simulated_sample", lambda t, gate: bad(t))
    with TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        ws.send_json({"mode": "simulation", "ai_consent": consent, "coaching": mode})
        while True:
            message = ws.receive_json()
            if message["type"] == "sample" and message["sample"]["t"] >= 6:
                ws.send_json({"type": "finish"})
            if message["type"] == "report":
                assert bool(message["report"]["interventions"]) == (mode != "passive")
                break
    mock.assert_not_called()


def test_finishing_or_disconnecting_cancels_pending_decision_and_restart_is_clean(monkeypatch):
    import pulsepilot.app as module

    started, cancelled = threading.Event(), threading.Event()

    async def slow(*args):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    monkeypatch.setenv("AGENT_MODE", "adaptive")
    monkeypatch.setattr(MetaProvider, "propose", slow)
    monkeypatch.setattr(agents, "configured", lambda: True)
    monkeypatch.setattr(agents, "analyze_report", AsyncMock(side_effect=lambda report: report))
    monkeypatch.setattr(module, "simulated_sample", lambda t, gate: bad(t))
    with TestClient(app) as client:
        for finish in (True, False):
            started.clear()
            cancelled.clear()
            with client.websocket_connect("/ws/measure", headers={"origin": "http://localhost:3000"}) as ws:
                ws.send_json({"mode": "simulation", "ai_consent": True, "coaching": "meta"})
                while True:
                    message = ws.receive_json()
                    if message.get("coaching_state") == "DECIDING":
                        break
                assert message["interventions"] == []
                assert started.wait(2)
                if finish:
                    ws.send_json({"type": "finish"})
                    assert ws.receive_json()["report"]["interventions"] == []
            assert cancelled.wait(2)
