import json

import httpx
import pytest
from test_sensing import good_sample

from pulsepilot import agents
from pulsepilot.reports import build_report
from pulsepilot.schemas import CoachDecision, Intervention, SessionConfig


async def test_no_key_preserves_numerical_report(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    report = build_report(SessionConfig(), [], [])
    result = await agents.analyze_report(report)
    assert result.analyst == "deterministic" and result.ai_status == "unavailable"
    assert result.stats == report.stats


async def test_invalid_evidence_rejected(monkeypatch):
    report = build_report(SessionConfig(), [], [])
    analysis = report.analysis.model_copy(deep=True)
    analysis.summary[0].evidence_ids = ["invented-evidence"]
    async def fake(*args): return analysis
    monkeypatch.setattr(agents, "structured", fake)
    assert (await agents.analyze_report(report)).analyst == "deterministic"


async def test_invented_improvement_rejected(monkeypatch):
    report = build_report(SessionConfig(), [], [])
    analysis = report.analysis.model_copy(deep=True)
    analysis.summary[0].text = "The intervention improved the signal."
    async def fake(*args): return analysis
    monkeypatch.setattr(agents, "structured", fake)
    assert (await agents.analyze_report(report)).analyst == "deterministic"


async def test_contradictory_coaching_rejected(monkeypatch):
    async def fake(*args): return CoachDecision(issue="motion", explanation="Keep still.")
    monkeypatch.setattr(agents, "structured", fake)
    intervention = Intervention(id="i", issue="dark", action="More light", started_at=5)
    assert await agents.enrich_coach(intervention, good_sample()) is None


async def test_meta_wire_format_and_validated_response(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-only-key")
    base = httpx.AsyncClient
    def respond(request):
        payload = json.loads(request.content)
        assert payload["model"] == "muse-spark-1.3"
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"]
        assert payload["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
        assert json.loads(payload["messages"][1]["content"]) == {"brightness": 20}
        assert "input_image" not in request.content.decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"issue":"dark","explanation":"Face a steady light."}'}}]})
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: base(transport=httpx.MockTransport(respond), **kwargs))
    result = await agents.structured(CoachDecision, {"brightness": 20}, "Explain conditions.")
    assert result.issue == "dark"


async def test_timeout_keeps_coaching_deterministic(monkeypatch):
    async def fail(*args): raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(agents, "structured", fail)
    item = Intervention(id="i", issue="dark", action="More light", started_at=5)
    assert await agents.enrich_coach(item, good_sample()) is None


@pytest.mark.parametrize("text", ["Your healthy heart is accurate.", "Your heart rate is 73.", "This diagnoses arrhythmia."])
def test_unsupported_text_rejected(text):
    assert not agents.safe_text(text)
