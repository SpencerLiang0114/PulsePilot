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

## Stable ten-second readings

PulsePilot now estimates BPM from the last 300 completed raw FacePhys BVP samples (ten seconds at the model's 30 Hz). The adapter removes linear drift, applies a zero-phase 0.5–3 Hz bandpass, and selects the strongest 40–180 BPM Welch spectral peak using the full window. It avoids upstream's peak-by-peak amplitude normalization. SQI is now autocorrelation near that selected period on the same filtered signal, rather than upstream's maximum autocorrelation on raw BVP. Thresholds remain heuristic; the changed SQI is not directly comparable to earlier exports and is not an accuracy probability. Weights and camera crops are unchanged.

The camera overlay and main BPM card share `display_bpm` and `display_state`. A first eligible estimate appears after acquisition, then the number refreshes every ten seconds using the median of eligible estimates from the preceding two seconds. Eligibility requires a fresh window, at least 24 capture FPS, SQI ≥0.35, a finite 40–180 BPM candidate, one visible unobstructed face, and acceptable brightness, flicker, and motion. Size, centering, angle, and light-imbalance advice continues without erasing the display. These less strict readings are labeled preliminary; they do not become accepted samples or enter accepted report statistics. The accepted gate and report-only preliminary gate retain their existing thresholds and camera checks, using the revised estimator outputs.

During a quality dip, the display labels the last estimate with its age and clears it once it is ten seconds old. Face loss, multiple faces, invalid capture conditions, inference lag, finish, and transport failures clear the display. A detector miss of at most 250 ms does not reset the acquisition timeline, although the reading is hidden while the face is absent. Longer misses and multiple faces require a new ten-second window. Thus the application reduces avoidable gaps; it cannot promise a number when no valid pulse is available.

Synthetic regression tests cover known 42–175 BPM signals with noise and slow illumination drift, broadband-noise rejection, display cadence and expiry, camera rejection, and brief tracking misses. These establish processing and display behavior, not improved real-camera/reference-device accuracy. A paired reference-device recording is still needed to assess accuracy and tune the new quality score.

## Live face heatmap

The camera/recording preview has a **Face heatmap** switch showing the FacePhys demo's first attention projection (`fm1`). The public `proj.tflite` graph takes `state_in_8`, reshapes it to 1×36×36×32, and averages the final (channel) axis. In the pinned Python model this is `state[0][1]["tn"]["x2mean"]`. We compute this reduction directly from the existing model state at the full 36×36 resolution. There is no square root, percentile normalization, RGB color-change extraction, or second inference model.

Projection provenance: [FacePhys-Demo at commit 0007a97565872f5845824802eccec0258305c98d](https://github.com/KegangWangCCNU/FacePhys-Demo/tree/0007a97565872f5845824802eccec0258305c98d), `models/proj.tflite`, SHA-256 `5ed4508ccbf0c90a603cf0daa04b5f4d97d766ddf799fbbd080bb2b81bb645fa`. The public [facephys.com projection](https://www.facephys.com/tflite/proj.tflite) was byte-identical when checked on October 21, 2026. A direct LiteRT interpreter comparison using a 36×36×32 float32 ramp matched the NumPy channel mean at `rtol=1e-6` (maximum absolute difference 0.000030517578125). This verifies the projection operation, not identical outputs across different checkpoints or camera pipelines.

Rendering adapts the website's [HeatmapOverlay](https://www.facephys.com/assets/index-CamBvO3D.js), retaining min/max range smoothing with alpha 0.05 and red/orange/yellow intensity. For clearer visibility on bright or smaller faces, saturated red begins earlier, yellow covers the upper 20% of the scale, values below 0.15 remain transparent, and opacity above that threshold uses a 0.35 power curve with 0.9 overall opacity. Normal alpha blending keeps red and yellow visible instead of washing them out against the camera image. Completed raw BVP samples drive a bounded brightness gain and soft forehead/cheek/nose highlights. These highlights approximate the demo's styling; they are decorative pulse-driven regions, not independent local measurements. Pulse normalization uses up to 60 samples and alpha 0.1 range smoothing after ten samples. Range and pulse history advance only on a new model timestamp, even when the same frame is emitted twice at 60 Hz. This is model attention, not measured skin color, blood flow, or temperature.

The full-range BlazeFace detector is used for both camera metrics and FacePhys crops, including smaller faces at a normal seated distance. Maps accept detector-confirmed faces (confidence at least 0.5) independently of the stricter heart-rate quality checks. Initial acquisition still requires 500 ms and nonflat, finite model features. Inference lag up to 750 ms is tolerated. A brief tracking miss holds the last real map, with its original model timestamp, for at most 1.25 seconds and shows “Reacquiring face…”; it does not restart visual warmup or normalization. Multiple faces, sustained loss, stale inference, invalid features, and model shutdown clear the map and reset display scaling. Heart-rate acceptance and its contiguous visibility window remain unchanged.

`face_heatmap` events target 60 Hz, bounded by capture throughput; FacePhys's state still updates at 30 Hz. Events carry capture-relative `t`, camera metrics, and `heatmap: {t, bbox, width: 36, height: 36, values: number[1296], pulse: number}` or `null`. Values encode normalized attention as 0–255; pulse is 0–1. The map follows the actual smoothed model crop. Video and overlay share contain/letterbox positioning and camera mirroring; recordings are not mirrored. The waveform sits below the video so it cannot obscure the face. The browser clears a map after 1.5 seconds without fresh events and on finish, cancellation, or error. Simulation produces no heatmap. Maps are transient and excluded from reports, exports, and Meta requests.

## Scrolling pulse waveform

Measurement samples carry paired `waveform` and `waveform_times` arrays. Times come from completed FacePhys samples and are converted to session-relative seconds, including after model restarts. Invalid values are removed together with their timestamps; the plot breaks the trace at timestamp gaps of 100 ms or more. Both arrays are stripped from stored reports.

The live graph uses a fixed eight-second window, labeled session-time ticks, a numeric normalized-BVP amplitude scale, hover values, and local-maximum markers (visual landmarks, not validated heartbeat detections). It fills from zero during the first eight seconds, then scrolls left. Between the 2 Hz sample messages, the display clock advances on animation frames, without generating signal values. If updates stop, clock interpolation stops after 750 ms; the existing measurement watchdog handles sustained stalls. Simulation uses the server-reported playback rate: 1× for consented adaptive planning, 4× for the ordinary demo. The displayed trace still updates at the measurement-message cadence.

## Licensing limitation

The repository [LICENSE](https://github.com/KegangWangCCNU/open-rppg/blob/4d24237e7b14e17429b49d0334f2282b7d2fd159/LICENSE) grants MIT terms to source/tools but explicitly reserves pretrained-model terms to the original authors/publications. There is no explicit FacePhys-specific checkpoint license in the inspected tree. Source MIT must not be described as blanket permission to redistribute weights or commercially deploy the model. Obtain author clarification before redistribution/commercial release.

## Validation

Separate checkpoint loading/JIT, finite output on synthetic input, real recorded-video extraction, live browser transport, and reference-device accuracy. A synthetic-input smoke test verifies execution only. No reference measurement has been supplied.

Camera capture requests 60 FPS (subject to camera/browser support); face sensing runs on each received frame. FacePhys retains its trained 30 Hz inference timeline.
