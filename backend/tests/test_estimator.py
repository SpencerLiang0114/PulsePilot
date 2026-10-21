from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from pulsepilot.estimator import FacePhysEstimator


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
    estimator.frame_count = 5
    estimator.push(frame, 2.1)
    assert estimator.visible_since == 2.1
