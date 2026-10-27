import asyncio

import pytest
from test_graph_state import coach_event, report_event

from pulsepilot.orchestration.contracts import AnalysisProposal, ClaimReference, CoachProposal
from pulsepilot.orchestration.graph import build_graphs
from pulsepilot.schemas import DECISION_EXPLANATIONS, Analysis


class FakeProvider:
    identifier = "fixture"

    async def propose(self, event):
        return CoachProposal(
            session_id=event.session_id, event_id=event.event_id, action_id="motion", issue_id="motion",
            reason="persistent_issue", explanation=DECISION_EXPLANATIONS["persistent_issue"],
        )

    async def analyze(self, event):
        return AnalysisProposal(session_id=event.session_id, event_id=event.event_id, **{
            section: [ClaimReference(claim_id=c.claim_id, evidence_id=c.evidence_id, claim_type=c.claim_type)
                      for c in event.bundle.claims if c.section == section][:4]
            for section in Analysis.model_fields
        })


async def test_compiled_graphs_accept_and_keep_trusted_inputs():
    coach, report = build_graphs(FakeProvider())
    for graph, event in ((coach, coach_event()), (report, report_event())):
        before = event.model_dump_json()
        result = await graph.ainvoke({"event": event})
        assert result["outcome"].route == "accepted"
        assert event.model_dump_json() == before
        assert result["event"] == event
        assert result["outcome"].model_dump_json()


async def test_noop_skips_provider():
    event = coach_event()
    event = event.model_copy(update={"context": event.context.model_copy(update={"candidates": []})})
    coach, _ = build_graphs(FakeProvider())
    result = await coach.ainvoke({"event": event})
    assert result["outcome"].route == "no_op" and "proposal" not in result


@pytest.mark.parametrize("error,status", [(ValueError("malformed"), "invalid"),
                                          (TimeoutError(), "timeout"), (RuntimeError("offline"), "unavailable")])
async def test_error_routes_to_deterministic_fallback(error, status):
    class Failed(FakeProvider):
        async def propose(self, event):
            raise error

        async def analyze(self, event):
            raise error

    graphs = build_graphs(Failed())
    for graph, event in zip(graphs, (coach_event(), report_event()), strict=True):
        outcome = (await graph.ainvoke({"event": event}))["outcome"]
        assert outcome.route == "fallback" and outcome.status == status
        if outcome.action:
            assert outcome.action.action_id == "dark" and outcome.action.source == "rules"
        else:
            assert outcome.analysis == event.bundle.baseline


async def test_parallel_sessions_share_graph_without_state():
    graph, _ = build_graphs(FakeProvider())
    events = [coach_event(), coach_event()]
    results = await asyncio.gather(*(graph.ainvoke({"event": e}) for e in events))
    assert [r["outcome"].session_id for r in results] == [e.session_id for e in events]
    assert results[0]["outcome"].event_id != results[1]["outcome"].event_id
