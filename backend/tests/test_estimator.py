from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from pulsepilot.estimator import FacePhysEstimator
from pulsepilot.schemas import CameraMetrics


def test_failed_start_closes_partially_initialized_workers(monkeypatch):
    import pulsepilot.estimator as module

    model = Mock()
    model.ift.ident = None
    model.__enter__ = Mock(side_effect=RuntimeError("detector initialization failed"))
    monkeypatch.setattr(module, "weights_available", lambda: True)
    monkeypatch.setattr(module.importlib, "import_module", lambda name: SimpleNamespace(Model=lambda name: model))
    estimator = FacePhysEstimator()
    with pytest.raises(RuntimeError, match="detector initialization"):
        estimator.start()
    assert estimator.model is None
    model.face_detection_pool.shutdown.assert_called_once_with(wait=True)
    assert model.face_resampling_pool.shutdown.call_count == 2
    assert model.alive is False


def test_start_rejects_an_already_running_model():
    estimator = FacePhysEstimator()
    estimator.model = object()
    with pytest.raises(RuntimeError, match="already"):
        estimator.start()


def test_start_uses_full_range_face_detector(monkeypatch):
    import pulsepilot.estimator as module

    model = Mock()
    model.__enter__ = Mock()
    monkeypatch.setattr(module, "weights_available", lambda: True)
    monkeypatch.setattr(module.importlib, "import_module", lambda name: SimpleNamespace(Model=lambda name: model))
    estimator = FacePhysEstimator()
    estimator.start()
    assert model.face_mode == "Far"
    estimator.close()


def test_close_is_idempotent_and_joins_both_worker_pools():
    model = Mock()
    estimator = FacePhysEstimator()
    estimator.model = model
    estimator.close()
    estimator.close()
    assert estimator.model is None
    assert model.alive is False
    model.face_detection_pool.shutdown.assert_called_once_with(wait=True)
    model.sp.release.assert_called_once()
    model.ift.join.assert_called_once()
    model.face_resampling_pool.shutdown.assert_called_once_with(wait=True)


def test_multiple_faces_restart_the_contiguous_measurement_window():
    box = np.array([100, 50, 220, 190])
    points = np.array([[140, 100], [180, 100], [160, 120], [160, 145], [120, 115], [200, 115]])
    face = (box, points, np.array([.98], dtype=np.float32))
    detector = SimpleNamespace(detect=lambda rgb: [face, face])
    estimator = FacePhysEstimator()
    estimator.model = SimpleNamespace(
        detector=detector, update_frame=lambda rgb, ts: None,
        face_detection_task=SimpleNamespace(result=lambda timeout: None),
        ift=SimpleNamespace(is_alive=lambda: True),
    )
    estimator.start_time = estimator.epoch = estimator.visible_since = 1.0
    estimator.last_timestamp = 1.9
    frame = np.full((240, 320, 3), 140, dtype=np.uint8)
    estimator.push(frame, 2.0)
    assert estimator.visible_since is None
    detector.detect = lambda rgb: [face]
    estimator.push(frame, 2.1)
    assert estimator.visible_since == 2.1


@pytest.fixture
def heatmap_estimator():
    estimator = FacePhysEstimator()
    variance = np.broadcast_to(np.arange(36*36).reshape(1, 1, 36, 36, 1), (1, 1, 36, 36, 32)).copy()
    estimator.model = SimpleNamespace(
        state=[[{}, {"tn": {"x2mean": variance}}]], n_signal=1, ts=[10.9],
        box=np.array([[40, 200], [80, 240]]),
    )
    estimator.frame_size = (240, 320)
    estimator.start_time = estimator.visible_since = 10
    estimator.last_timestamp = 11
    estimator.camera = CameraMetrics(face_visible=True, face_count=1, confidence=.98)
    return estimator


def test_heatmap_matches_demo_fm1_projection_and_actual_crop(heatmap_estimator):
    heatmap = heatmap_estimator.heatmap()
    assert heatmap.t == .9
    assert heatmap.bbox == [80/320, 40/240, 240/320, 200/240]
    assert heatmap.width == heatmap.height == 36 and len(heatmap.values) == 1296
    assert min(heatmap.values) == 0 and max(heatmap.values) == 255
    assert heatmap.values[324] == round(324/1295*255)
    assert heatmap.pulse == .5


@pytest.mark.parametrize("condition", ["lost", "multiple", "low_confidence", "lag", "warmup", "empty", "flat", "nan"])
def test_heatmap_hides_unusable_or_uninitialized_features(heatmap_estimator, condition):
    estimator = heatmap_estimator
    if condition == "lost":
        estimator.camera.face_visible = False
    elif condition == "multiple":
        estimator.camera.face_count = 2
    elif condition == "low_confidence":
        estimator.camera.confidence = .4
    elif condition == "lag":
        estimator.last_timestamp = 12
    elif condition == "warmup":
        estimator.visible_since = 10.8
    elif condition == "empty":
        estimator.model.n_signal = 0
    else:
        estimator.model.state[0][1]["tn"]["x2mean"] = np.full((1, 1, 36, 36, 32), np.nan if condition == "nan" else 1)
    assert estimator.heatmap() is None


def test_heatmap_accepts_detector_confirmed_distant_face_and_normal_inference_delay(heatmap_estimator):
    estimator = heatmap_estimator
    estimator.camera.confidence = .65
    estimator.camera.face_size = .15
    estimator.camera.brightness = 40
    estimator.last_timestamp = 11.3
    assert estimator.heatmap() is not None


def test_heatmap_holds_brief_tracking_loss_without_restarting_visual_warmup(heatmap_estimator):
    estimator = heatmap_estimator
    original = estimator.heatmap()
    estimator.camera.face_visible = False
    estimator.visible_since = None
    estimator.last_timestamp = 12
    assert estimator.heatmap() == original
    assert estimator.heatmap_range is not None
    estimator.camera.face_visible = True
    estimator.visible_since = 12.1
    estimator.last_timestamp = 12.1
    estimator.model.ts = [12.05]
    assert estimator.heatmap().t == 2.05


@pytest.mark.parametrize("condition", ["expired", "multiple", "lag"])
def test_heatmap_hold_never_survives_sustained_loss_multiple_faces_or_stalled_model(heatmap_estimator, condition):
    estimator = heatmap_estimator
    assert estimator.heatmap() is not None
    if condition == "expired":
        estimator.camera.face_visible = False
        estimator.last_timestamp = 12.3
    elif condition == "multiple":
        estimator.camera.face_count = 2
    else:
        estimator.last_timestamp = 12
    assert estimator.heatmap() is None
    assert estimator.heatmap_range is None


def test_heatmap_smooths_range_once_per_model_frame(heatmap_estimator):
    estimator = heatmap_estimator
    estimator.heatmap()
    variance = estimator.model.state[0][1]["tn"]["x2mean"]
    estimator.model.state[0][1]["tn"]["x2mean"] = variance*2
    estimator.model.ts = [11]
    first = estimator.heatmap()
    assert estimator.heatmap_range == pytest.approx((0, 1295*1.05))
    second = estimator.heatmap()
    assert first.values == second.values
    assert estimator.heatmap_range == pytest.approx((0, 1295*1.05))
    estimator.camera.face_count = 2
    assert estimator.heatmap() is None
    assert estimator.heatmap_range is None


def test_heatmap_brightness_tracks_completed_bvp_only(heatmap_estimator):
    estimator = heatmap_estimator
    estimator.model.signal_buff = {"bvp": []}
    for i in range(10):
        timestamp = 10.9+i/30
        estimator.last_timestamp = timestamp
        estimator.model.ts = [timestamp]
        estimator.model.signal_buff["bvp"] = [i/10]
        heatmap = estimator.heatmap()
    assert heatmap.pulse > .5
    estimator.heatmap()
    assert len(estimator.heatmap_pulses) == 10


def test_waveform_timestamps_preserve_session_offset_and_missing_values():
    estimator = FacePhysEstimator()
    estimator.start_time, estimator.epoch, estimator.last_timestamp = 10, 14, 16.1
    estimator.model = SimpleNamespace(
        n_signal=60, ts=np.linspace(14, 16, 60).tolist(), signal_buff={"bvp": [0]*60},
        bvp=lambda **kwargs: ([1, np.nan, -1], np.array([1.9, 1.95, 2.0])),
    )
    sample = estimator.snapshot()
    assert sample.waveform == [1, -1]
    assert sample.waveform_times == pytest.approx([5.9, 6.0])
    assert sample.processing_ms == 0
    assert sample.inference_lag_ms == 100


def test_no_completed_inference_has_unavailable_lag():
    estimator = FacePhysEstimator()
    estimator.start_time = estimator.epoch = estimator.last_timestamp = 10
    estimator.model = SimpleNamespace(n_signal=0, ts=[], signal_buff={"bvp": []})
    sample = estimator.snapshot()
    assert sample.bpm is None and not sample.usable
    assert sample.inference_lag_ms is None


def test_snapshot_estimates_from_completed_raw_bvp_without_upstream_reshaping():
    from test_sensing import good_sample

    estimator = FacePhysEstimator()
    estimator.start_time = estimator.epoch = estimator.visible_since = 0
    estimator.last_timestamp = 10.1
    estimator.camera = good_sample().camera
    estimator.timestamps.extend(np.linspace(8, 10.1, 64))
    times = np.arange(301)/30
    bvp = np.sin(2*np.pi*1.2*times)
    estimator.model = SimpleNamespace(
        n_signal=301, ts=times.tolist(), signal_buff={"bvp": bvp.tolist()},
        bvp=Mock(side_effect=lambda **kwargs: (bvp, times)),
    )
    sample = estimator.snapshot()
    assert sample.display_bpm == pytest.approx(72, abs=1)
    assert sample.sqi > .55
    assert estimator.model.bvp.call_args_list[0].kwargs["raw"] is True


def test_brief_detector_miss_does_not_restart_ten_second_acquisition():
    box = np.array([100, 50, 220, 190])
    points = np.array([[140, 100], [180, 100], [160, 120], [160, 145], [120, 115], [200, 115]])
    faces = [(box, points, np.array([.98], dtype=np.float32))]
    estimator = FacePhysEstimator()
    estimator.model = SimpleNamespace(
        detector=SimpleNamespace(detect=lambda rgb: faces), update_frame=lambda rgb, ts: None,
        face_detection_task=SimpleNamespace(result=lambda timeout: None),
        ift=SimpleNamespace(is_alive=lambda: True),
    )
    frame = np.full((240, 320, 3), 140, dtype=np.uint8)
    estimator.push(frame, 1)
    faces.clear()
    estimator.push(frame, 1.1)
    assert estimator.visible_since == 1
    assert not estimator.camera.face_visible
    faces.append((box, points, np.array([.98], dtype=np.float32)))
    estimator.push(frame, 1.2)
    assert estimator.visible_since == 1
    faces.clear()
    estimator.push(frame, 1.3)
    estimator.push(frame, 1.4)
    estimator.push(frame, 1.5)
    assert estimator.visible_since is None
