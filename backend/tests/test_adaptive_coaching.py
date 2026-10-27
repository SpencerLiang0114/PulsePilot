from uuid import uuid4

import pytest
from test_graph_routing import FakeProvider
from test_sensing import good_sample
from test_sensing_agent import bad, decision, proposal

from pulsepilot.coaching import MeasurementCoach
from pulsepilot.orchestration.service import OrchestrationService, as_decision
from pulsepilot.schemas import DecisionResult


async def test_graph_selection_commits_once_and_carries_measured_outcomes():
    coach, context = proposal()
    service = OrchestrationService(mode="adaptive", ai_consent=True, provider=FakeProvider())
    outcome = await service.run_coach_event(service.coach_event(context, "select"))
    assert coach.active is None and not coach.interventions
    sample = bad(5.5)
    coach.update(sample)
    item = coach.resolve(context.proposal_id, as_decision(outcome), sample, 100)
    assert item.action_id == "motion" and item.started_at == 5.5
    assert coach.resolve(context.proposal_id, as_decision(outcome), sample, 100) is None
    for i in range(12, 44):
        coach.update(bad(i*.5))
    assert item.outcome == "unchanged" and item.evaluated_at == 13.5
    event = service.coach_event(coach.proposal, "select")
    assert event.context.outcomes[0].action_id == "motion"
    assert event.context.outcomes[0].outcome == "unchanged"
    assert all(s.t < item.started_at for s in coach.baseline)
    assert coach.proposal.sample_at >= item.evaluated_at+8
    assert all(c.action_id != "motion" for c in event.context.candidates)
    await service.close()


async def test_proposal_from_another_session_cannot_be_accepted():
    class CrossSession(FakeProvider):
        async def propose(self, event):
            return (await super().propose(event)).model_copy(update={"session_id": str(uuid4())})

    coach, context = proposal()
    service = OrchestrationService(mode="adaptive", ai_consent=True, provider=CrossSession())
    outcome = await service.run_coach_event(service.coach_event(context, "select"))
    assert outcome.status == "identity_mismatch"
    sample = bad(5.5)
    coach.update(sample)
    item = coach.resolve(context.proposal_id, as_decision(outcome), sample, 100)
    assert item.action_id == "dark" and item.decision_source == "rules"


def test_capture_timeline_expiry_uses_current_rules_not_late_model_selection():
    coach, context = proposal()
    for t in (5.5, 6, 6.5, 7):
        coach.update(bad(t))
    item = coach.resolve(context.proposal_id, DecisionResult(status="selected", decision=decision()),
                         coach.history[-1], 100)
    assert item.action_id == "dark" and item.decision_status == "fallback_timeout"


@pytest.mark.parametrize("change", ["resolved", "face_loss", "gap", "finish"])
async def test_conditions_are_revalidated_after_graph_returns(change):
    coach, context = proposal()
    service = OrchestrationService(mode="adaptive", ai_consent=True, provider=FakeProvider())
    outcome = await service.run_coach_event(service.coach_event(context, "select"))
    sample = bad(5.5)
    if change == "resolved":
        sample = good_sample(t=5.5)
    elif change == "face_loss":
        sample.camera.face_visible = False
    elif change == "gap":
        sample.t = 8
    else:
        coach.finish(5)
    coach.update(sample)
    assert coach.resolve(context.proposal_id, as_decision(outcome), sample, 100) is None
    assert not coach.interventions


@pytest.mark.parametrize("sqi,outcome", [(None, "inconclusive"), (.3, "unchanged"),
                                        (.7, "improved"), (.1, "worsened")])
def test_outcome_windows_and_no_overlap_remain_deterministic(sqi, outcome):
    coach, context = proposal()
    sample = bad(5.5)
    coach.update(sample)
    item = coach.resolve(context.proposal_id, DecisionResult(status="selected", decision=decision()), sample, 100)
    for i in range(12, 28):
        coach.update(bad(i*.5, sqi=sqi))
        assert len(coach.interventions) == 1
    assert item.outcome == outcome
    assert item.before_sqi == .3
    assert item.after_sqi == sqi
    assert coach.cooldown_until == item.evaluated_at+8
    coach.update(bad(14))
    assert coach.proposal is None


def test_prior_history_is_bounded_and_inconclusive_never_suppresses_retry():
    coach = MeasurementCoach()
    for t in range(200):
        sample = bad(float(t), sqi=None)
        coach.update(sample)
    assert len(coach.memory.records) == 6
    assert all(r.outcome == "inconclusive" for r in coach.memory.records)
    assert coach.memory.unsuccessful == {}
