import importlib
import math
import os
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np

from .schemas import CameraMetrics, FaceHeatmap, Sample
from .sensing import CameraSensing, ReliabilityGate

ROOT = Path(os.getenv("FACEPHYS_ROOT", Path(__file__).resolve().parents[2] / ".vendor/open-rppg"))
HEATMAP_TRACKING_GRACE = 1.25
HEATMAP_MAX_LAG = 0.75


def weights_available() -> bool:
    return (ROOT / "rppg/weights/FacePhys.rlap.weights.h5").is_file()


def finite(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


class FacePhysEstimator:
    def __init__(self):
        self.model = None
        self.start_time = None
        self.last_timestamp = None
        self.epoch = None
        self.visible_since = None
        self.timestamps = deque(maxlen=90)
        self.sensing = CameraSensing()
        self.camera = CameraMetrics()
        self.gate = ReliabilityGate()
        self.processing_ms = 0.0
        self.frame_size = (0, 0)
        self.heatmap_range = None
        self.heatmap_timestamp = None
        self.heatmap_pulses = deque(maxlen=60)
        self.heatmap_pulse_range = (0.0, 1.0)
        self.heatmap_pulse = 0.5
        self.last_heatmap = None
        self.last_heatmap_seen = None

    def start(self):
        if self.model is not None:
            raise RuntimeError("FacePhys is already initialized.")
        if not weights_available():
            raise RuntimeError("FacePhys weights are missing. Run uv run scripts/fetch_facephys.py.")
        os.environ.setdefault("KERAS_BACKEND", "jax")
        os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        rppg = importlib.import_module("rppg")
        model = rppg.Model("FacePhys.rlap")
        # Upstream closes detection but leaves this constructor-created executor open.
        model.face_resampling_pool.shutdown(wait=True)
        model.face_detection_threads = 2
        model.face_resampling_threads = 2
        # The full-range detector also covers smaller faces at a normal seated distance.
        model.face_mode = "Far"
        self.model = model
        try:
            model.__enter__()
        except Exception:
            self.close()
            raise

    def close(self):
        self.reset_heatmap()
        if self.model is not None:
            model, self.model = self.model, None
            try:
                # Drain detection before stopping inference, including on partial startup.
                model.face_detection_pool.shutdown(wait=True)
            finally:
                model.alive = False
                model.sp.release()
                try:
                    worker = getattr(model, "ift", None)
                    if worker is not None and worker.ident is not None:
                        worker.join()
                finally:
                    model.face_resampling_pool.shutdown(wait=True)

    def push(self, rgb: np.ndarray, timestamp: float):
        if self.model is None:
            raise RuntimeError("FacePhys is not initialized.")
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("Invalid capture timestamp.")
        if self.last_timestamp is not None and timestamp <= self.last_timestamp:
            raise ValueError("Capture timestamps must increase.")
        if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("Expected uint8 RGB frames.")
        began = time.perf_counter()
        if self.last_timestamp is not None and timestamp-self.last_timestamp > 0.25:
            self.close()
            self.start()
            self.timestamps.clear()
            self.epoch = timestamp
            self.visible_since = None
            self.sensing = CameraSensing()
            self.gate = ReliabilityGate()
        if self.start_time is None:
            self.start_time = timestamp
            self.epoch = timestamp
        self.last_timestamp = timestamp
        self.frame_size = rgb.shape[:2]
        self.timestamps.append(timestamp)
        detections = self.model.detector.detect(rgb)
        self.camera = self.sensing.assess(rgb, detections, timestamp)
        if not self.camera.face_visible or self.camera.face_count != 1:
            self.visible_since = None
        elif self.visible_since is None:
            self.visible_since = timestamp
        self.model.update_frame(rgb, ts=timestamp)
        self.model.face_detection_task.result(timeout=5)
        if not self.model.ift.is_alive():
            raise RuntimeError("The FacePhys inference worker stopped. Restart measurement.")
        self.processing_ms = (time.perf_counter()-began)*1000

    def reset_heatmap(self):
        self.heatmap_range = None
        self.heatmap_timestamp = None
        self.heatmap_pulses.clear()
        self.heatmap_pulse_range = (0.0, 1.0)
        self.heatmap_pulse = 0.5
        self.last_heatmap = None
        self.last_heatmap_seen = None

    def heatmap(self) -> FaceHeatmap | None:
        model = self.model
        if (model is None or self.last_timestamp is None or model.box is None
                or self.camera.face_count > 1):
            self.reset_heatmap()
            return None
        if (not self.camera.face_visible or self.camera.face_count != 1
                or self.camera.confidence < 0.5 or self.visible_since is None):
            # Hold the last real attention map through brief detector misses; never invent new values.
            if (self.last_heatmap is not None
                    and self.last_timestamp-self.last_heatmap_seen <= HEATMAP_TRACKING_GRACE):
                return self.last_heatmap
            self.reset_heatmap()
            return None
        count = min(model.n_signal, len(model.ts))
        if not count:
            self.reset_heatmap()
            return None
        timestamp = model.ts[count-1]
        if (self.last_timestamp-timestamp > HEATMAP_MAX_LAG
                or (self.last_heatmap is None and timestamp-self.visible_since < 0.5)):
            self.reset_heatmap()
            return None
        # FacePhys demo proj.tflite fm1: state_in_8 -> reshape -> mean(channels).
        state = model.state
        variance = np.asarray(state[0][1]["tn"]["x2mean"])[0, 0]
        if variance.shape != (36, 36, 32) or not np.isfinite(variance).all():
            self.reset_heatmap()
            return None
        attention = variance.mean(axis=-1)
        low, high = float(attention.min()), float(attention.max())
        if high-low < 1e-6:
            self.reset_heatmap()
            return None
        if timestamp != self.heatmap_timestamp:
            if self.heatmap_range is None:
                self.heatmap_range = (low, high)
            else:
                old_low, old_high = self.heatmap_range
                self.heatmap_range = (.95*old_low + .05*low, .95*old_high + .05*high)
            bvp = getattr(model, "signal_buff", {}).get("bvp", [])
            pulse = finite(bvp[count-1]) if len(bvp) >= count else None
            if pulse is not None:
                self.heatmap_pulses.append(pulse)
                if len(self.heatmap_pulses) >= 10:
                    lo, hi = self.heatmap_pulse_range
                    lo = .9*lo + .1*min(self.heatmap_pulses)
                    hi = .9*hi + .1*max(self.heatmap_pulses)
                    self.heatmap_pulse_range = (lo, hi)
                    self.heatmap_pulse = float(np.clip((pulse-lo)/(hi-lo), 0, 1)) if hi-lo >= .01 else .5
            self.heatmap_timestamp = timestamp
        low, high = self.heatmap_range
        values = np.rint(np.clip((attention-low)/(high-low), 0, 1)*255).astype(np.uint8)
        h, w = self.frame_size
        box = np.asarray(model.box, dtype=float).copy()
        x1, x2 = np.clip(box[1], 0, w)/w
        y1, y2 = np.clip(box[0], 0, h)/h
        if x2 <= x1 or y2 <= y1:
            return None
        self.last_heatmap = FaceHeatmap(t=round(timestamp-self.start_time, 3),
                                       bbox=[float(x1), float(y1), float(x2), float(y2)],
                                       values=values.reshape(-1).tolist(), pulse=self.heatmap_pulse)
        self.last_heatmap_seen = self.last_timestamp
        return self.last_heatmap

    def snapshot(self) -> Sample:
        model = self.model
        if model is None or self.last_timestamp is None:
            return Sample(t=0)
        elapsed = self.last_timestamp-self.start_time
        visible_start = self.visible_since if self.visible_since is not None else self.last_timestamp
        fresh = self.last_timestamp-max(self.epoch, visible_start)
        stamps = np.asarray(self.timestamps)
        fps = float((len(stamps)-1)/(stamps[-1]-stamps[0])) if len(stamps) > 1 else 0
        candidate, sqi, wave, wave_times = None, None, [], []
        # Only read samples the upstream worker has completed; queries stay on its timeline.
        count = min(model.n_signal, len(model.signal_buff.get("bvp", [])), len(model.ts))
        if count >= 300:
            end = model.ts[count-1]-model.ts[0]
            start = max(0, end-10)
            result = model.hr(start=start, end=end, return_hrv=False)
            if result:
                candidate, sqi = finite(result.get("hr")), finite(result.get("SQI"))
                sqi = max(0, min(1, sqi)) if sqi is not None else None
        if count >= 60:
            end = model.ts[count-1]-model.ts[0]
            values, times = model.bvp(start=max(0, end-8), end=end)
            for value, timestamp in zip(values[-240:], times[-240:], strict=True):
                if math.isfinite(float(value)) and math.isfinite(float(timestamp)):
                    wave.append(float(value))
                    wave_times.append(float(timestamp + model.ts[0] - self.start_time))
        lag = max(0, self.last_timestamp-model.ts[count-1]) if count else 0
        sample = Sample(t=round(elapsed, 3), sqi=sqi, fps=round(fps, 1),
                        latency_ms=round(self.processing_ms + lag*1000, 1),
                        processing_ms=round(self.processing_ms, 1),
                        inference_lag_ms=round(lag*1000, 1) if count else None,
                        camera=self.camera.model_copy(deep=True), waveform=wave, waveform_times=wave_times)
        if lag > 0.5:
            fresh = 0
        return self.gate.apply(sample, candidate, fresh)
