from types import SimpleNamespace

import numpy as np

from pulsepilot.estimator import FacePhysEstimator


def test_multiple_faces_restart_the_contiguous_measurement_window():
    box = np.array([100, 50, 220, 190])
    points = np.array([[140, 100], [180, 100], [160, 120], [160, 145], [120, 115], [200, 115]])
    face = (box, .98, points)
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
