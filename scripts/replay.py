"""Replay a user-supplied video through the same adapter and numerical reporting path."""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import av
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from pulsepilot.coaching import MeasurementCoach
from pulsepilot.estimator import FacePhysEstimator
from pulsepilot.reports import build_report
from pulsepilot.schemas import SessionConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--coaching", choices=["passive", "rules"], default="rules")
    parser.add_argument("--reference", type=Path, help="Optional synchronized CSV: t,bpm (seconds from video start)")
    args = parser.parse_args()
    estimator = FacePhysEstimator()
    coach = MeasurementCoach(passive=args.coaching == "passive")
    samples = []
    estimator.start()
    start = time.monotonic()
    first = None
    last_sample = -1.0
    try:
        with av.open(str(args.video)) as container:
            for frame in container.decode(video=0):
                if frame.time is None:
                    raise ValueError("Recording needs presentation timestamps.")
                if first is None:
                    first = frame.time
                timestamp = frame.time-first
                if timestamp > 180:
                    break
                # Preserve real-time capture cadence and allow the model worker to finish.
                delay = timestamp-(time.monotonic()-start)
                if delay > 0:
                    time.sleep(delay)
                estimator.push(frame.to_ndarray(format="rgb24"), timestamp)
                if timestamp-last_sample >= .49:
                    sample = estimator.snapshot()
                    samples.append(sample)
                    coach.update(sample)
                    last_sample = timestamp
        coach.finish(samples[-1].t if samples else 0)
        report = build_report(SessionConfig(mode="recording", coaching=args.coaching), samples, coach.interventions)
        result = report.model_dump()
        if args.reference:
            with args.reference.open() as handle:
                reference = sorted((float(row["t"]), float(row["bpm"])) for row in csv.DictReader(handle))
            errors = []
            for sample in samples:
                if sample.bpm is None or not sample.usable or not reference:
                    continue
                nearest = min(reference, key=lambda point: abs(point[0]-sample.t))
                if abs(nearest[0]-sample.t) <= .5 and np.isfinite(nearest[1]):
                    errors.append(abs(nearest[1]-sample.bpm))
            result["reference_comparison"] = {
                "matched_windows": len(errors), "mae_bpm": float(np.mean(errors)) if errors else None,
                "alignment": "Nearest timestamp within 0.5 seconds; timestamps supplied by the operator",
            }
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False))
        print(f"Saved {len(samples)} observation windows to {args.output}. No raw frames saved.")
    finally:
        estimator.close()


if __name__ == "__main__":
    main()
