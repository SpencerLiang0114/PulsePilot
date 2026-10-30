import numpy as np
import pytest

from pulsepilot.reports import build_report, measurement_evidence
from pulsepilot.schemas import Sample, SessionConfig
from pulsepilot.variability import pulse_variability


def waveform_samples(duration=80, alternating=True):
    intervals = np.resize([.75, .85] if alternating else [.8], 140)
    beats = np.cumsum(intervals)
    times = np.arange(0, duration + 1 / 30, 1 / 30)
    values = np.sum(np.exp(-((times[:, None] - beats) / .07) ** 2), axis=1)
    samples = []
    for t in range(8, duration + 1):
        mask = (times >= t - 8) & (times <= t)
        samples.append(Sample(t=t, bpm=75, sqi=.9, usable=True, fps=30,
            waveform=values[mask].tolist(), waveform_times=times[mask].tolist()))
    return samples


def test_known_alternating_intervals_and_overlapping_windows():
    result = pulse_variability(waveform_samples(), "camera")
    assert result.status == "available"
    assert result.rmssd_ms == pytest.approx(100, abs=5)
    assert result.sdnn_ms == pytest.approx(50, abs=3)
    assert 85 <= result.interval_count <= 90  # Each pulse counted once, not once per window.
    assert min(result.intervals_ms) > 700
    assert len(set(result.interval_times)) == result.interval_count


def test_constant_intervals_have_near_zero_variability():
    result = pulse_variability(waveform_samples(alternating=False), "recording")
    assert result.status == "available"
    assert result.rmssd_ms < 1
    assert result.sdnn_ms < 1


@pytest.mark.parametrize("kind", ["rejected", "missing", "stale", "timestamps", "flat", "nonfinite", "slow"])
def test_bad_windows_and_gaps_never_join_short_segments(kind):
    samples = waveform_samples(duration=65)
    for s in samples:
        if not 25 <= s.t <= 45:
            continue
        if kind == "rejected":
            s.usable = False
        elif kind == "missing":
            s.waveform_times = []
        elif kind == "stale":
            s.waveform_times = [t - 2 for t in s.waveform_times]
        elif kind == "timestamps":
            s.waveform_times[10] = s.waveform_times[9]
        elif kind == "flat":
            s.waveform = [0] * len(s.waveform)
        elif kind == "nonfinite":
            s.waveform[10] = float("nan")
        else:
            s.fps = 20
    if kind == "missing":
        samples = [s for s in samples if not 25 <= s.t <= 45]
    result = pulse_variability(samples, "camera")
    assert result.status == "insufficient"
    assert result.rmssd_ms is None and result.sdnn_ms is None
    assert result.duration < 30


def test_no_waveform_short_data_and_simulation_do_not_invent_hrv():
    for samples in ([], [Sample(t=t, bpm=75, usable=True) for t in range(80)], waveform_samples(30)):
        assert pulse_variability(samples, "camera").rmssd_ms is None
    assert pulse_variability(waveform_samples(), "simulation").status == "simulation"


def test_missed_beats_split_intervals_instead_of_inflating_variability():
    samples = waveform_samples(duration=80, alternating=False)
    # Remove the same beat in every overlapping window that contains it.
    for s in samples:
        times = np.asarray(s.waveform_times)
        s.waveform = (np.asarray(s.waveform) - np.exp(-((times - 40) / .07) ** 2)).tolist()
    result = pulse_variability(samples, "camera")
    assert result.status == "available"
    assert result.rejected_intervals >= 1
    assert result.duration < 40
    assert result.rmssd_ms < 1
    assert max(result.intervals_ms) < 850


def test_wrong_peak_frequency_is_not_accepted_as_variability():
    samples = waveform_samples()
    for s in samples:
        s.bpm = 150  # Detected pulses at 75 BPM disagree with accepted HR.
    assert pulse_variability(samples, "camera").status == "insufficient"


def test_report_preserves_metrics_and_interval_evidence_after_stripping_waveforms():
    report = build_report(SessionConfig(mode="camera"), waveform_samples(), [])
    result = report.pulse_variability
    assert result.status == "available"
    assert all(not s.waveform and not s.waveform_times for s in report.samples)
    assert measurement_evidence(report).pulse_variability == result
    assert any(i.insight_id == "pulse_variability" for i in report.health_insights.insights)
    assert report.model_dump(mode="json")["pulse_variability"]["intervals_ms"]
