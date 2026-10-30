"""Exploratory pulse-rate variability from timestamped, accepted BVP windows.

Detect peaks within each window (never concatenate independently filtered BVP).
Commit only new, interior peaks. Never join intervals across rejected windows,
timestamp gaps, or rejected beats. Product gates are not clinical validation.
"""
import numpy as np
from scipy.signal import find_peaks

from .schemas import PulseVariability, Sample


def pulse_variability(samples: list[Sample], mode: str) -> PulseVariability:
    if mode == "simulation":
        return PulseVariability(status="simulation", reason="Synthetic data cannot measure your HRV.")
    runs: list[list[float]] = []
    run: list[float] = []
    start = None
    committed_until = -float("inf")
    previous_t = None
    for sample in samples:
        times = np.asarray(sample.waveform_times, dtype=float)
        values = np.asarray(sample.waveform, dtype=float)
        valid = (sample.usable and sample.bpm is not None and sample.fps >= 24
                 and len(times) == len(values) and len(times) >= 60
                 and np.isfinite(times).all() and np.isfinite(values).all())
        if valid:
            steps = np.diff(times)
            valid = (np.all(steps > 0) and np.max(steps) <= .1
                     and np.median(steps) <= 1 / 24 + 1e-6
                     and 0 <= sample.t - times[-1] <= .5
                     and np.std(values) > 1e-8)
        if not valid or (previous_t is not None and not 0 < sample.t - previous_t <= 1.5):
            if run:
                runs.append(run)
            run, start = [], None
        previous_t = sample.t
        if not valid:
            continue
        if start is None:
            start = sample.t
        # The trailing quarter-second is revisited in the next overlapping window.
        cutoff = times[-1] - .25
        peaks, _ = find_peaks(values, distance=max(1, int(.3 / np.median(steps))),
                              prominence=.5 * np.std(values))
        for peak in peaks:
            if peak == 0 or peak == len(times) - 1:
                continue
            # Sub-frame timing from a local parabola on actual timestamps.
            local_t = times[peak-1:peak+2] - times[peak]
            a, b, _ = np.polyfit(local_t, values[peak-1:peak+2], 2)
            offset = -b / (2 * a) if a < 0 else 0
            timestamp = float(times[peak] + np.clip(offset, local_t[0], local_t[-1]))
            if max(start, committed_until) < timestamp <= cutoff:
                # Reject a detected rate grossly inconsistent with the accepted HR.
                if run and timestamp - run[-1] < .25:
                    continue
                run.append(timestamp)
        committed_until = max(committed_until, cutoff)
    if run:
        runs.append(run)

    clean_runs: list[tuple[np.ndarray, np.ndarray]] = []
    rejected = 0
    accepted_bpms = [s.bpm for s in samples if s.usable and s.bpm is not None]
    expected = 60000 / float(np.median(accepted_bpms)) if accepted_bpms else 0
    for peaks in runs:
        intervals = np.diff(peaks) * 1000
        end_times = np.asarray(peaks[1:])
        if not len(intervals):
            continue
        # Local outliers split segments: removing a beat must not create a new
        # artificial successive pair for RMSSD. No ectopic-beat diagnosis here.
        local = np.array([np.median(intervals[max(0, i-2):i+3]) for i in range(len(intervals))])
        valid = ((intervals >= 60000 / 180) & (intervals <= 1500)
                 & (np.abs(intervals - local) <= .2 * local)
                 & (np.abs(local - expected) <= .2 * expected))
        rejected += int(np.sum(~valid))
        begin = 0
        for i in range(len(intervals) + 1):
            if i == len(intervals) or not valid[i]:
                if i > begin:
                    clean_runs.append((end_times[begin:i], intervals[begin:i]))
                begin = i + 1
    if not clean_runs:
        return PulseVariability(rejected_intervals=rejected)
    times, intervals = max(clean_runs, key=lambda pair: float(np.sum(pair[1])))
    duration = float(np.sum(intervals) / 1000)
    if duration < 30 or len(intervals) < 30:
        return PulseVariability(duration=round(duration, 2), interval_count=len(intervals),
            rejected_intervals=rejected,
            reason="At least 30 continuous seconds and 30 accepted pulse intervals are needed. "
                   "Short or interrupted BVP segments cannot support this estimate.")
    return PulseVariability(status="available",
        reason="Longest continuous segment passing pulse-timing checks; short-recording estimate, not clinically validated.",
        rmssd_ms=round(float(np.sqrt(np.mean(np.diff(intervals) ** 2))), 2),
        sdnn_ms=round(float(np.std(intervals, ddof=1)), 2), duration=round(duration, 2),
        interval_count=len(intervals), rejected_intervals=rejected,
        interval_times=tuple(round(float(t), 4) for t in times),
        intervals_ms=tuple(round(float(v), 3) for v in intervals))
