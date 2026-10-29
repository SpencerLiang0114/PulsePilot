import importlib
from pathlib import Path

import pytest
from test_graph_routing import FakeProvider

from pulsepilot.coaching import MeasurementCoach
from pulsepilot.orchestration.service import OrchestrationService
from pulsepilot.schemas import DECISION_EXPLANATIONS


@pytest.mark.parametrize("result", ["selected", "abstained", "invalid", "obsolete"])
async def test_live_harness_distinguishes_validation_from_actual_commitment(monkeypatch, result):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    harness = importlib.import_module("verify_sensing_agent")
    coach = MeasurementCoach(mode="meta")
    for i in range(11):
        coach.update(harness.scenario(i*.5))

    class Provider(FakeProvider):
        async def propose(self, event):
            proposal = await super().propose(event)
            if result == "invalid":
                return proposal.model_copy(update={"issue_id": "dark"})
            if result == "abstained":
                return proposal.model_copy(update={"action_id": None, "issue_id": None, "reason": "wait",
                                                   "explanation": DECISION_EXPLANATIONS["wait"]})
            return proposal

    if result == "obsolete":
        original = harness.scenario

        def resolved(t):
            sample = original(t)
            sample.camera.motion = 0
            return sample

        monkeypatch.setattr(harness, "scenario", resolved)
    service = OrchestrationService(mode="adaptive", ai_consent=True, provider=Provider())
    try:
        record = await harness.opportunity(service, coach)
        summary = harness.summarize([record], 1)
        assert not summary["p3_target_met"]  # A diagnostic run cannot satisfy the declared batch size.
        assert summary["muse_commitments"] == (1 if result == "selected" else 0)
        assert summary["rules_commitments"] == (1 if result == "invalid" else 0)
        assert summary["applied_abstentions"] == (1 if result == "abstained" else 0)
        assert record["category"] == ("invalid_response" if result == "invalid" else
                                       "valid_abstention" if result == "abstained" else "accepted_selection")
        assert not record["provider_response_received"]  # The fixture has no HTTP transfer.
        assert not record["provider_latency_complete"]
    finally:
        await service.close()
