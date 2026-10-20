"""Deterministic software-demo fixture. Never used as a real estimator fallback."""
import math

from .schemas import CameraMetrics, Sample
from .sensing import ReliabilityGate


def simulated_sample(t: float, gate: ReliabilityGate) -> Sample:
    dark = 5 <= t < 12
    moving = 27 <= t < 35
    quality = None if t < 10 else (0.32 if dark else 0.39 if moving else 0.84 + 0.03*math.sin(t/7))
    camera = CameraMetrics(
        face_visible=True, face_count=1, confidence=0.98, face_size=0.48,
        center_offset=0.03, visibility_proxy=0.98,
        brightness=40 if dark else 142, light_imbalance=8, motion=0.45 if moving else 0.025,
        bbox=[0.33, 0.2, 0.67, 0.68],
    )
    bpm = 72 + 1.8*math.sin(t/13)
    wave = [math.sin(2*math.pi*(bpm/60)*(t-8+i/30)) + 0.22*math.sin(4*math.pi*(bpm/60)*(t-8+i/30))
            for i in range(240)] if t > 2 else []
    sample = Sample(t=t, sqi=quality, fps=30, latency_ms=18, camera=camera, waveform=wave)
    return gate.apply(sample, bpm, t)
