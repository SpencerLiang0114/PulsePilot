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
- Detection returns `(bounding_box, six_landmarks, confidence)`, with confidence stored as a one-element NumPy array. These support approximate pose/visibility feedback; they are not a dense face mesh or a validated occlusion detector.
- The public model uses asynchronous buffers and silently reports some exceptions from worker threads. The adapter checks inference-worker liveness and available signal length, reads completed samples conservatively, bounds sessions, and closes both executors.

## Dependencies and installation

Use uv with Python 3.12. Upstream requires JAX, Keras, onnxruntime, OpenCV, SciPy, heartpy, einops, and av. Its source imports `pkg_resources`; constrain setuptools below the release that removed it. Set `KERAS_BACKEND=jax` and disable XLA preallocation. Pin the actual tested dependency set in `backend/uv.lock`.

The upstream repository has no Python packaging metadata. Fetch its pinned commit into ignored `.vendor/open-rppg` using `scripts/fetch_facephys.py`, then load that source from the adapter. Fetching keeps checkpoint provenance explicit and avoids committing third-party weights here. There is no fine-tuning or change to model architecture, weights, or crops.

## Adapter contract

`FacePhysEstimator.start()` initializes/warmups and rejects duplicate startup. `push(rgb, timestamp)` checks monotonic timestamps, handles large gaps, and feeds the original RGB image. `snapshot()` exposes finite BVP/HR/SQI plus camera metrics and measured cadence. `close()` drains detection, stops and joins inference, then closes the resampling pool; it also handles a partially failed context startup. The adapter manages that shutdown sequence because upstream context exit assumes successful startup. All calls for one adapter run serially off the async event loop, and request cancellation waits for in-flight model work before releasing resources or capacity. See the [backend service protocol](backend-service.md).

Require at least ten seconds of fresh data and acceptable capture cadence, face visibility, lighting, motion, and periodicity before showing an estimate. Keep raw candidate HR separate from accepted HR. Short/invalid windows yield `null`, never a plausible default.

## Live face heatmap

The camera/recording preview has a **Face heatmap** switch. The backend reads the frozen model's first spatial block, second layer's temporal-normalization variance (`state[0][1]["tn"]["x2mean"]`, 36×36×32). It averages channels, takes the square root, downsamples to 18×18, and scales the fifth–ninety-fifth percentile range into 0–255 for the red/yellow overlay. This is relative temporal feature activity, not the official demo's attention projection, a calibrated optical spectrum, blood-flow map, or skin temperature. Per-map normalization means colors are not comparable between sessions or frames. Motion and lighting changes can also produce activity.

The existing inference state is reused without changing weights, crops, BVP, or heart-rate acceptance. The overlay uses the model's actual smoothed crop rather than the separate coaching detector's box. Video and overlay share contain/letterbox positioning and camera mirroring; recording playback is not mirrored.

`face_heatmap` WebSocket events target 30 Hz, limited by capture and inference throughput, separately from measurement samples. At most one event is emitted per 1/30-second capture-time interval; slower input does not generate duplicate frames. Each contains `heatmap: {t, bbox, width: 18, height: 18, values: number[324]}` or `null`. Coordinates are normalized to the transmitted frame; `t` is the latest completed model timestamp relative to session start. Maps are withheld during initial/reacquisition warmup, multiple/missing faces, low detector confidence, more than 200 ms of inference lag, and flat/nonfinite feature maps. The browser removes a map after 750 ms without a newer map and on finish, cancellation, or error. Turning the switch off hides rendering while sensing continues. Simulation produces no heatmap. Maps are transient, excluded from reports, exports, and Meta requests.

The [author's browser demo](https://github.com/KegangWangCCNU/FacePhys-Demo) uses a separate `proj.tflite` model for spatial projections; the pinned Python integration has no public heatmap API. This implementation reads existing temporal features instead of installing a second model or claiming equivalent attention outputs.

## Licensing limitation

The repository [LICENSE](https://github.com/KegangWangCCNU/open-rppg/blob/4d24237e7b14e17429b49d0334f2282b7d2fd159/LICENSE) grants MIT terms to source/tools but explicitly reserves pretrained-model terms to the original authors/publications. There is no explicit FacePhys-specific checkpoint license in the inspected tree. Source MIT must not be described as blanket permission to redistribute weights or commercially deploy the model. Obtain author clarification before redistribution/commercial release.

## Validation

Separate checkpoint loading/JIT, finite output on synthetic input, real recorded-video extraction, live browser transport, and reference-device accuracy. A synthetic-input smoke test verifies execution only. No reference measurement has been supplied.
