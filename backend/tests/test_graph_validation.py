import json
from unittest.mock import AsyncMock

import httpx
import pytest
from test_graph_routing import FakeProvider
from test_graph_state import coach_event, report_event

from pulsepilot import agents
from pulsepilot.orchestration.contracts import AnalysisProposal, CoachProposal
from pulsepilot.orchestration.graph import build_graphs
from pulsepilot.orchestration.provider import MetaProvider
from pulsepilot.orchestration.validation import validate_action, validate_claims


@pytest.mark.parametrize("change,reason", [
    ({"event_id": "00000000-0000-0000-0000-000000000000"}, "identity_mismatch"),
    ({"action_id": "bright", "issue_id": "bright"}, "ineligible_action"),
    ({"issue_id": "dark"}, "ineligible_action"),
    ({"explanation": "Your pulse is accurate and healthy."}, "unsupported_explanation"),
    ({"reason": "try_alternative", "explanation": "A previous correction did not improve periodicity; try another eligible correction."}, "unsupported_outcome"),
])
async def test_action_validation_is_semantic_and_identity_bound(change, reason):
    event = coach_event()
    proposed = (await FakeProvider().propose(event)).model_copy(update=change)
    assert validate_action(event, proposed).reason == reason


@pytest.mark.parametrize("change", [
    {"claim_id": "invented-stable-pulse"}, {"evidence_id": "missing"},
    {"claim_type": "signal_available"}, {"claim_type": "intervention_improved"},
])
async def test_empty_report_cannot_support_invented_facts(change):
    event = report_event()
    proposal = await FakeProvider().analyze(event)
    bad = proposal.summary[0].model_copy(update=change)
    proposal = proposal.model_copy(update={"summary": [bad]})
    assert not validate_claims(event, proposal).valid
    assert event.bundle.stats.mean_bpm is None
    assert event.bundle.claims[0].claim_type == "signal_unavailable"


async def test_duplicate_and_cross_section_claims_fail():
    event = report_event()
    output = await FakeProvider().analyze(event)
    assert not validate_claims(event, output.model_copy(update={"quality": output.summary})).valid
    assert not validate_claims(event, output.model_copy(update={"summary": output.summary*2})).valid


@pytest.mark.parametrize("schema", [CoachProposal, AnalysisProposal])
async def test_extra_prose_or_stats_cannot_enter_model_contract(schema):
    event = coach_event() if schema is CoachProposal else report_event()
    valid = await (FakeProvider().propose(event) if schema is CoachProposal else FakeProvider().analyze(event))
    for change in ({"text": "Your heart is healthy."}, {"stats": {"mean_bpm": 72}},
                   {"explanation": "The correct action is to exercise."} if schema is AnalysisProposal
                   else {"action_id": "exercise"}):
        data = {**valid.model_dump(), **change}
        with pytest.raises(ValueError):
            schema.model_validate(data)


async def test_meta_adapter_uses_existing_endpoint_and_strict_schema(monkeypatch):
    event = coach_event()
    valid = await FakeProvider().propose(event)
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    base = httpx.AsyncClient

    def respond(request):
        wire = json.loads(request.content)
        assert str(request.url) == agents.META_URL
        assert wire["model"] == "muse-spark-1.3"
        schema = wire["response_format"]["json_schema"]["schema"]
        assert schema["additionalProperties"] is False
        assert "session_id" in schema["required"]
        payload = json.loads(wire["messages"][1]["content"])
        assert payload["event_id"] == event.event_id
        assert "waveform" not in request.content.decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": valid.model_dump_json()}}],
                                       "usage": {"prompt_tokens": 11, "completion_tokens": 7}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: base(transport=httpx.MockTransport(respond), **kwargs))
    assert await MetaProvider().propose(event) == valid


async def test_no_consent_makes_zero_http_calls(monkeypatch):
    mock = AsyncMock(side_effect=AssertionError("unauthorized request"))
    monkeypatch.setattr(agents, "structured", mock)
    graph, _ = build_graphs(MetaProvider())
    outcome = (await graph.ainvoke({"event": coach_event(ai_consent=False)}))["outcome"]
    assert outcome.route == "fallback"
    mock.assert_not_called()


@pytest.mark.parametrize("content", ["not json", "{}", '{"action_id":"fabricated"}'])
async def test_bad_model_json_falls_back(monkeypatch, content):
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    base = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: base(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    ), **kwargs))
    coach, _ = build_graphs(MetaProvider())
    assert (await coach.ainvoke({"event": coach_event()}))["outcome"].route == "fallback"
