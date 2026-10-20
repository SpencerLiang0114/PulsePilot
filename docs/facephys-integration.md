# Verified FacePhys integration

Source: [open-rppg](https://github.com/KegangWangCCNU/open-rppg), inspected commit `4d24237e7b14e17429b49d0334f2282b7d2fd159` on October 20, 2026.

## Source findings

- `rppg/main.py`: `Model("FacePhys.rlap")` selects the pretrained model.
- `rppg/models.py:1792`: `load_FacePhys_rlap()` loads `weights/FacePhys.rlap.weights.h5`, creates a JAX-jitted stateful callable, and warms it with two zero frames. Input is `(1, 36, 36, 3)`, RGB uint8 before scaling, nominal rate 30 Hz. The checkpoint is present (about 3 MB).
- `Model.__enter__()` starts face detection, resampling, and inference workers. Use a fresh model instance/context per session; never share mutable temporal state.
- `update_frame(rgb, ts=seconds)` performs detection/crop/resampling. It accepts external frames; there is no need for `video_capture()`.
- `bvp(start=…, raw=False)` returns BVP and relative timestamps; `hr(start=…, return_hrv=False)` returns `hr`, `SQI`, `hrv`, and `latency`, or `None`. Disable HRV in this short-session MVP.
- The API's `SQI` is autocorrelation periodicity, not an accuracy probability. Its calculation can produce nonfinite results for constant signals; guard every output.
- The implementation fills/skips frames to reach 30 Hz. Sparse input can create apparently periodic signals; gate on actual capture cadence and gaps separately.
- Detection returns a bounding box, confidence, and six landmarks. These support approximate pose/visibility feedback; they are not a dense face mesh or a validated occlusion detector.
- The public model uses asynchronous buffers and silently reports some exceptions from worker threads. The adapter checks inference-worker liveness and available signal length, reads completed samples conservatively, bounds sessions, and closes both executors.

## Dependencies and installation

Use uv with Python 3.12. Upstream requires JAX, Keras, onnxruntime, OpenCV, SciPy, heartpy, einops, and av. Its source imports `pkg_resources`; constrain setuptools below the release that removed it. Set `KERAS_BACKEND=jax` and disable XLA preallocation. Pin the actual tested dependency set in `backend/uv.lock`.

The upstream repository has no Python packaging metadata. Fetch its pinned commit into ignored `.vendor/open-rppg` using `scripts/fetch_facephys.py`, then load that source from the adapter. Fetching keeps checkpoint provenance explicit and avoids committing third-party weights here. There is no fine-tuning or change to model architecture, weights, or crops.

## Adapter contract

`FacePhysEstimator.start()` initializes/warmups. `push(rgb, timestamp)` checks monotonic timestamps, handles large gaps, and feeds the original RGB image. `snapshot()` exposes finite BVP/HR/SQI plus camera metrics and measured cadence. `close()` drains and releases resources. All calls for one adapter run serially off the async event loop.

Require at least ten seconds of fresh data and acceptable capture cadence, face visibility, lighting, motion, and periodicity before showing an estimate. Keep raw candidate HR separate from accepted HR. Short/invalid windows yield `null`, never a plausible default.

## Licensing limitation

The repository [LICENSE](https://github.com/KegangWangCCNU/open-rppg/blob/4d24237e7b14e17429b49d0334f2282b7d2fd159/LICENSE) grants MIT terms to source/tools but explicitly reserves pretrained-model terms to the original authors/publications. There is no explicit FacePhys-specific checkpoint license in the inspected tree. Source MIT must not be described as blanket permission to redistribute weights or commercially deploy the model. Obtain author clarification before redistribution/commercial release.

## Validation

Separate checkpoint loading/JIT, finite output on synthetic input, real recorded-video extraction, live browser transport, and reference-device accuracy. A synthetic-input smoke test verifies execution only. No reference measurement has been supplied.
