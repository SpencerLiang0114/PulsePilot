import pytest
from test_sensing import good_sample

from pulsepilot.coaching import MeasurementCoach
from pulsepilot.reports import build_report
from pulsepilot.schemas import SessionConfig
from pulsepilot.sensing import ReliabilityGate
from pulsepilot.simulation import simulated_sample


def test_disjoint_windows_and_cooldown():
    coach = MeasurementCoach()
    for i in range(51):
        t = i*.5
        sample = good_sample(t=t, sqi=.3 if t < 8 else .85)
        sample.camera.motion = .5 if t < 8 else 0
        coach.update(sample)
    assert len(coach.interventions) == 1
    item = coach.interventions[0]
    assert item.outcome == "improved"
    assert item.before_sqi == pytest.approx(.3)
    assert item.after_sqi > .7
    assert item.evaluated_at >= item.started_at+8
    assert all(s.t < item.started_at for s in coach.baseline)


def test_early_finish_is_inconclusive():
    coach = MeasurementCoach()
    for i in range(17):
        sample = good_sample(t=i*.5, sqi=None)
        sample.camera.brightness = 20
        coach.update(sample)
    coach.finish(8)
    assert coach.interventions[0].outcome == "inconclusive"
    assert coach.interventions[0].delta is None


def test_good_setup_remains_quiet_and_passive_never_intervenes():
    coach = MeasurementCoach()
    passive = MeasurementCoach(passive=True)
    for i in range(100):
        coach.update(good_sample(t=i*.5))
        bad = good_sample(t=i*.5)
        bad.camera.motion = 1
        passive.update(bad)
    assert coach.interventions == passive.interventions == []


def test_empty_report_has_no_fabricated_numbers():
    report = build_report(SessionConfig(), [], [])
    assert report.stats.mean_bpm is None
    assert report.stats.min_bpm is None
    assert report.stats.usable_fraction == 0
    assert report.stats.stable_at is None
    assert report.analyst == "deterministic"


def test_report_excludes_invalid_estimates_and_preserves_provenance():
    samples = [good_sample(t=10), good_sample(t=11), good_sample(t=12)]
    samples[0].bpm, samples[0].usable = 70, True
    samples[1].bpm, samples[1].usable = 999, False
    samples[2].bpm, samples[2].usable = 74, True
    report = build_report(SessionConfig(mode="simulation"), samples, [])
    assert report.stats.mean_bpm == 72
    assert report.stats.median_bpm == 72
    assert report.stats.min_bpm == 70 and report.stats.max_bpm == 74
    assert report.mode == "simulation"
    assert report.stats.usable_fraction == pytest.approx(2/3)


def test_simulation_produces_report_with_actual_logged_outcomes():
    gate, coach = ReliabilityGate(), MeasurementCoach()
    samples = [simulated_sample(i*.5, gate) for i in range(121)]
    for sample in samples:
        coach.update(sample)
    coach.finish(60)
    report = build_report(SessionConfig(mode="simulation"), samples, coach.interventions)
    assert report.stats.mean_bpm is not None
    assert report.stats.usable_fraction < 1
    assert len(report.interventions) >= 2
    for section in report.analysis.model_dump().values():
        for item in section:
            assert all(ref in report.evidence for ref in item["evidence_ids"])


def test_preliminary_points_survive_export_without_changing_accepted_statistics():
    gate = ReliabilityGate()
    samples = [gate.apply(good_sample(t=12+i*.5, sqi=.4), 90, 12+i*.5) for i in range(3)]
    report = build_report(SessionConfig(), samples, [])
    assert report.stats.mean_bpm is None
    assert report.stats.usable_fraction == 0
    assert report.stats.stable_at is None
    assert all(s["report_bpm"] == 90 and s["bpm"] is None for s in report.model_dump()["samples"])
    assert "3 preliminary report windows" in report.evidence["report_trend"]
    for i in range(3):
        samples.append(gate.apply(good_sample(t=14+i*.5), 70, 14+i*.5))
    report = build_report(SessionConfig(), samples, [])
    assert report.stats.mean_bpm == 70
    assert report.stats.usable_fraction == pytest.approx(1/6)
