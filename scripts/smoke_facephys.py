"""Real checkpoint execution on synthetic frames; this is NOT accuracy validation."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from pulsepilot.estimator import FacePhysEstimator


def main():
    estimator = FacePhysEstimator()
    began = time.perf_counter()
    estimator.start()
    warmup = time.perf_counter()-began
    try:
        model = estimator.model
        state = model.state
        # Direct frozen-checkpoint execution verifies finite outputs without claiming a face.
        values = []
        started = time.perf_counter()
        for i in range(360):
            frame = np.full((1, 36, 36, 3), 120 + 5*np.sin(i/30*2*np.pi), dtype=np.uint8)
            out, state = model.call(frame, state)
            values.extend(np.asarray(out["bvp"]).reshape(-1).tolist())
        inference_seconds = time.perf_counter()-started
        assert len(values) == 360 and np.isfinite(values).all()
        for i in range(330):
            estimator.push(np.full((240, 320, 3), 100, dtype=np.uint8), i/30)
        time.sleep(0.2)
        result = estimator.snapshot()
        assert result.bpm is None and not result.usable and not result.camera.face_visible
        print(json.dumps({"checkpoint": "FacePhys.rlap", "warmup_seconds": round(warmup, 2),
                          "model_fps": round(360/inference_seconds, 1), "finite_bvp_samples": len(values),
                          "blank_frame_bpm": result.bpm, "blank_frame_state": result.state,
                          "accuracy_validated": False}, indent=2))
    finally:
        estimator.close()


if __name__ == "__main__":
    main()
