import importlib
from pathlib import Path

import pytest


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("evaluate_p2")


async def test_policy_ablation_uses_the_same_trace_without_inventing_user_response(harness):
    samples = harness.trace(27)
    results = [await harness.evaluate(condition, [s.model_copy(deep=True) for s in samples]) for condition in "ABC"]
    for name in ("mean_sqi", "usable_fraction", "time_to_stable_seconds"):
        assert len({r["metrics"][name] for r in results}) == 1
    assert results[0]["action_sequence"] == results[1]["action_sequence"]
    assert results[0]["action_sequence"][0] == "dark"
    assert results[2]["action_sequence"][0] == "motion"
    assert all(r["metrics"]["api_requests"] == 0 for r in results)
    assert all(r["resources"]["measurement_throughput_fps"] is None for r in results)
    assert all(r["metrics"]["approximate_cost_usd"] is None for r in results)
    assert results[2]["metrics"]["proposal_acceptance_rate"] == 1


def test_empty_report_has_missing_telemetry_instead_of_assumed_usage(harness):
    from pulsepilot.reports import build_report
    from pulsepilot.schemas import Intervention, SessionConfig

    result = harness.metrics(build_report(SessionConfig(), [], []), [])
    assert result["mean_sqi"] is None and result["time_to_stable_seconds"] is None
    assert result["proposal_acceptance_rate"] is None
    assert result["graph_latency_ms"] is None
    assert result["api_requests"] is None and result["input_tokens"] is None
    report = build_report(SessionConfig(), [], [])
    report.interventions = [Intervention(id="early", issue="dark", action="Face a light.",
                                         started_at=10, evaluated_at=12, outcome="inconclusive")]
    early = harness.metrics(report, [])
    assert early["intervention_completion_rate"] == 0
    assert early["outcomes"] == {"inconclusive": 1}
    assert early["mean_delta_usable"] is None


async def test_exported_telemetry_preserves_observed_usage_and_no_payload(harness):
    from pulsepilot.orchestration.service import OrchestrationService
    from pulsepilot.reports import build_report
    from pulsepilot.schemas import SessionConfig

    report = build_report(SessionConfig(), [], [])
    runner = OrchestrationService(ai_consent=True, provider=harness.FixtureProvider())
    await runner.run_report_event(runner.report_event(report))
    report.agent_telemetry = runner.telemetry.snapshot()
    assert len(report.agent_telemetry) == 1
    exported = harness.exported_telemetry(report)
    assert harness.metrics(report, exported)["api_requests"] == 0
    assert "bundle" not in report.agent_telemetry[0].model_dump_json()
    await runner.close()
