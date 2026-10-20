import numpy as np
import pytest

from pulsepilot.schemas import CameraMetrics, Sample
from pulsepilot.sensing import CameraSensing, ReliabilityGate, issues


def good_sample(t=12, sqi=0.8, fps=30):
    return Sample(t=t, sqi=sqi, fps=fps, camera=CameraMetrics(
        face_visible=True, face_count=1, face_size=.5, visibility_proxy=.98, brightness=140))


def test_stable_requires_three_windows_and_hides_immediately_on_face_loss():
    gate = ReliabilityGate()
    assert gate.apply(good_sample(), 72, 12).bpm is None
    assert gate.apply(good_sample(), 72, 12).bpm is None
    assert gate.apply(good_sample(), 72, 12).bpm == 72
    lost = good_sample()
    lost.camera.face_visible = False
    assert gate.apply(lost, 72, 12).bpm is None
    assert not gate.stable


@pytest.mark.parametrize("candidate,sqi,fps,fresh", [
    (72, .9, 10, 12), (72, .9, 30, 5), (float("nan"), .9, 30, 12),
    (None, .9, 30, 12), (72, None, 30, 12), (72, .1, 30, 12), (250, .9, 30, 12),
])
def test_invalid_signal_never_displays_bpm(candidate, sqi, fps, fresh):
    gate = ReliabilityGate()
    for _ in range(4):
        result = gate.apply(good_sample(sqi=sqi, fps=fps), candidate, fresh)
        assert result.bpm is None and not result.usable


def test_hysteresis_holds_then_drops():
    gate = ReliabilityGate()
    for _ in range(3):
        gate.apply(good_sample(), 72, 12)
    assert gate.apply(good_sample(sqi=.50), 72, 12).usable
    assert not gate.apply(good_sample(sqi=.40), 72, 12).usable


def test_detection_metrics_and_no_face_reset():
    sensor = CameraSensing()
    image = np.full((240, 320, 3), 140, dtype=np.uint8)
    points = np.array([[140, 100], [180, 100], [160, 120], [160, 145], [120, 115], [200, 115]])
    result = sensor.assess(image, [(np.array([100, 50, 220, 190]), .98, points)], 1)
    assert result.face_visible and result.brightness == 140
    assert abs(result.yaw_proxy) < .01 and result.roll_degrees == 0
    assert result.light_imbalance == 0
    assert not sensor.assess(image, [], 2).face_visible
    assert sensor.previous is None


def test_dominant_issue_and_acceptable_setup():
    assert issues(good_sample()) == []
    bad = good_sample()
    bad.camera.face_visible = False
    bad.camera.brightness = 0
    assert issues(bad) == ["face"]
