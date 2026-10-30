import math
from collections import deque
from dataclasses import dataclass
from statistics import median

import numpy as np

from .schemas import CameraMetrics, CandidateAction, Sample


@dataclass(frozen=True)
class Thresholds:
    min_window: float = 10.0
    min_fps: float = 24.0
    sqi_enter: float = 0.55
    sqi_exit: float = 0.45
    report_sqi: float = 0.35
    report_min_fps: float = 20.0
    center_offset: float = 0.18
    min_size: float = 0.23
    max_size: float = 0.70
    max_motion: float = 0.28
    min_brightness: float = 55
    max_brightness: float = 225
    max_imbalance: float = 45


THRESHOLDS = Thresholds()

ACTIONS = {
    "face": "Bring your whole face into the guide, with no other faces in view.",
    "visibility": "Keep your forehead and cheeks visible; move anything covering your face.",
    "position": "Move into the center of the guide so your whole face stays in view.",
    "far": "Move a little closer to the camera.",
    "close": "Move a little farther from the camera.",
    "angle": "Face the camera directly and keep your head level.",
    "dark": "Face a window or a lamp to brighten your face.",
    "bright": "Move away from direct light so your face is not overexposed.",
    "uneven": "Place the light in front of you so both sides of your face are evenly lit.",
    "flicker": "Use a steady light source and avoid changing the screen brightness.",
    "motion": "Rest comfortably and keep your head still for the next few seconds.",
    "cadence": "Close other camera apps and tabs to help the camera keep a steady frame rate.",
    "signal": "Stay still a little longer while the pulse signal settles.",
}

# Only these scalar observations are sent to the decision endpoint.
ISSUE_METRICS = {
    "face": ("face_visible", "face_count"),
    "visibility": ("visibility_proxy",), "position": ("center_offset",),
    "far": ("face_size",), "close": ("face_size",),
    "angle": ("yaw_proxy", "roll_degrees"), "dark": ("brightness",),
    "bright": ("brightness",), "uneven": ("light_imbalance",),
    "flicker": ("light_change",), "motion": ("motion",),
    "cadence": ("fps",), "signal": ("sqi",),
}


def observations(sample: Sample) -> dict[str, float | bool]:
    values = sample.camera.model_dump(exclude={"bbox", "landmarks"})
    return {**values, "fps": sample.fps, **({"sqi": sample.sqi} if sample.sqi is not None else {})}


def candidate_actions(sample: Sample, persistent: set[str]) -> list[CandidateAction]:
    detected = issues(sample)
    # Face validity and capture cadence are handled by deterministic policy.
    safety = next((issue for issue in ("face", "cadence") if issue in detected), None)
    eligible = [safety] if safety else detected
    metrics = observations(sample)
    return [CandidateAction(
        action_id=issue, issue=issue, instruction=ACTIONS[issue], priority=list(ACTIONS).index(issue),
        observations={key: metrics[key] for key in ISSUE_METRICS[issue] if key in metrics},
    ) for issue in eligible if issue in persistent]


def issues(sample: Sample) -> list[str]:
    c, t = sample.camera, THRESHOLDS
    if not c.face_visible or c.face_count != 1:
        return ["face"]
    found = []
    if c.visibility_proxy < 0.7:
        found.append("visibility")
    if c.center_offset > t.center_offset:
        found.append("position")
    if c.face_size < t.min_size:
        found.append("far")
    elif c.face_size > t.max_size:
        found.append("close")
    if abs(c.yaw_proxy) > 0.35 or abs(c.roll_degrees) > 15:
        found.append("angle")
    if c.brightness < t.min_brightness:
        found.append("dark")
    elif c.brightness > t.max_brightness:
        found.append("bright")
    if c.light_imbalance > t.max_imbalance:
        found.append("uneven")
    if c.light_change > 25:
        found.append("flicker")
    if c.motion > t.max_motion:
        found.append("motion")
    if sample.t > 3 and sample.fps < t.min_fps:
        found.append("cadence")
    if sample.t >= 12 and (sample.sqi is None or sample.sqi < t.sqi_enter):
        found.append("signal")
    return found


class CameraSensing:
    """Six detector landmarks provide geometric proxies, not a calibrated 3-D pose."""

    def __init__(self):
        self.previous = None
        self.lights = deque(maxlen=15)

    def assess(self, rgb: np.ndarray, detections, timestamp: float) -> CameraMetrics:
        if not len(detections):
            self.previous = None
            self.lights.clear()
            return CameraMetrics()
        box, points, score = detections[0]
        confidence = float(np.asarray(score).item())
        h, w = rgb.shape[:2]
        x1, y1, x2, y2 = np.asarray(box, dtype=float)
        crop = rgb[max(0, int(y1)):min(h, int(y2)), max(0, int(x1)):min(w, int(x2))]
        if crop.size == 0:
            return CameraMetrics()
        gray = crop.astype(float).mean(axis=2)
        center = np.array([(x1+x2)/(2*w), (y1+y2)/(2*h)])
        motion = 0.0
        if self.previous:
            prev_t, prev_center = self.previous
            motion = float(np.linalg.norm(center-prev_center) / max(timestamp-prev_t, 0.03))
        self.previous = (timestamp, center)
        light = float(gray.mean())
        self.lights.append(light)
        points = np.asarray(points).reshape(-1, 2)
        eye1, eye2, nose = points[:3]
        eye_span = max(float(np.linalg.norm(eye2-eye1)), 1)
        eye_delta = eye2-eye1
        roll = math.degrees(math.atan2(float(eye_delta[1]), abs(float(eye_delta[0])) + 1e-6))
        inside = ((points[:, 0] >= 0) & (points[:, 0] <= w) &
                  (points[:, 1] >= 0) & (points[:, 1] <= h))
        fully_visible = x1 >= 0 and y1 >= 0 and x2 <= w and y2 <= h
        split = max(1, gray.shape[1]//2)
        imbalance = abs(float(gray[:, :split].mean())-float(gray[:, split:].mean())) if gray.shape[1] > 1 else 0
        return CameraMetrics(
            face_visible=True, face_count=len(detections), confidence=float(confidence),
            center_offset=float(np.linalg.norm(center-[0.5, 0.48])),
            face_size=float((y2-y1)/h),
            yaw_proxy=float((nose[0]-(eye1[0]+eye2[0])/2)/eye_span),
            roll_degrees=roll, brightness=light, light_imbalance=imbalance,
            light_change=float(np.std(self.lights)), motion=motion,
            visibility_proxy=float(min(float(confidence), float(inside.mean()), 1 if fully_visible else 0.5)),
            bbox=[float(x1/w), float(y1/h), float(x2/w), float(y2/h)],
            landmarks=(points / [w, h]).tolist(),
        )


class ReliabilityGate:
    def __init__(self):
        self.stable = False
        self.good_count = 0
        self.display_candidates = deque()
        self.display_bpm = None
        self.display_updated = None
        self.display_valid = None
        self.display_preliminary = True

    def apply(self, sample: Sample, candidate: float | None, fresh_seconds: float) -> Sample:
        t = THRESHOLDS
        detected = issues(sample)
        camera_ok = not [issue for issue in detected if issue != "signal"]
        threshold = t.sqi_exit if self.stable else t.sqi_enter
        capture_valid = (camera_ok and fresh_seconds >= t.min_window and sample.fps >= t.min_fps
                         and candidate is not None and math.isfinite(candidate) and 40 <= candidate <= 180)
        valid = capture_valid and sample.sqi is not None and sample.sqi >= threshold
        self.good_count = self.good_count + 1 if valid else 0
        self.stable = bool(valid and (self.stable or self.good_count >= 3))
        sample.usable = self.stable
        sample.bpm = round(candidate, 1) if self.stable else None
        # Report-only preliminary estimates never change live acceptance or coaching outcomes.
        report_capture_valid = (not [issue for issue in detected if issue not in {"signal", "cadence"}]
                                and fresh_seconds >= t.min_window and sample.fps >= t.report_min_fps
                                and candidate is not None and math.isfinite(candidate) and 40 <= candidate <= 180)
        sample.report_bpm = (round(candidate, 1) if report_capture_valid and sample.sqi is not None
                             and sample.sqi >= t.report_sqi else None)
        sample.state = ("Signal stable" if self.stable else
                        "Adjust your position" if not camera_ok else
                        "Measuring" if fresh_seconds < t.min_window else "Low confidence")
        # Position/size/angle advice should not erase a periodic pulse from a visible face.
        display_safe = (not set(detected).intersection({"face", "visibility", "dark", "bright",
                                                       "flicker", "motion", "cadence"})
                        and fresh_seconds >= t.min_window and sample.fps >= t.min_fps)
        if not display_safe:
            self.display_candidates.clear()
            self.display_bpm = self.display_updated = self.display_valid = None
        else:
            while self.display_candidates and self.display_candidates[0][0] < sample.t-2:
                self.display_candidates.popleft()
            if (candidate is not None and math.isfinite(candidate) and 40 <= candidate <= 180
                    and sample.sqi is not None and sample.sqi >= t.report_sqi):
                self.display_valid = sample.t
                self.display_candidates.append((sample.t, candidate))
                if self.display_updated is None or sample.t-self.display_updated >= 10:
                    self.display_bpm = round(median(value for _, value in self.display_candidates), 1)
                    self.display_updated = sample.t
                    self.display_preliminary = not sample.usable
            if self.display_updated is not None and sample.t-self.display_updated >= 10:
                self.display_bpm = self.display_updated = self.display_valid = None
                self.display_candidates.clear()
        sample.display_bpm = self.display_bpm
        if self.display_bpm is not None:
            age = sample.t-self.display_updated
            sample.display_state = (f"Last estimate · {age:.0f}s ago · reacquiring signal"
                                    if self.display_valid != sample.t else
                                    "Preliminary · 10s window" if self.display_preliminary else
                                    "10s window · updates every 10s")
        return sample
