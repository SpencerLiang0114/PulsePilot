# P4 — Repeatable real-camera measurement

October 28, 2026. **Completed for the declared local self-test:** three consecutive consenting physical-camera sessions completed and exported without restarting the backend. Motion/face-loss degradation and recovery were observed. Low-light robustness remains unestablished for the reasons below. Generated frames, recordings, and model-only benchmarks do not satisfy the physical-session requirement.

## Procedure

Use the same hardware, browser, camera, duration, and coaching mode for all three runs. Keep the tab foreground. Select **90 seconds**, **Rules** coaching, and explicit frame consent. AI consent is unnecessary for this capture/lifecycle check. The local inference service processes frames in memory; no video or audio is saved. Keep individual JSON exports outside the public repository.

Follow the on-page capture timer in every run:

| Capture time | Condition |
|---|---|
| 0–25 seconds | Stable front lighting; sit still, centered, with the whole face visible |
| 25–40 seconds | Reduce lighting while keeping position steady |
| 40–50 seconds | Restore lighting and move the head gently |
| 50–55 seconds | Move the face out of view; verify BPM disappears immediately |
| 55–90 seconds | Return to position and remain still under stable front lighting |

At completion, expand **Capture & delivery diagnostics** and export JSON. Verify camera release and `/health` reporting `busy: false`. Choose **Start a new measurement** and repeat twice without restarting the backend. Record failed attempts and deviations; if a fix is necessary, start a new declared consecutive batch after the fix.

For the October 28 self-test, the participant chose a split-condition sequence instead: run 1 is a stable baseline; run 2 uses dim lighting throughout while remaining still and centered; run 3 covers stable lighting, motion, face absence, and recovery. This exercises the P4 conditions across the consecutive batch without claiming that the original within-run lighting schedule was followed. For run 3, use 0–30 seconds stable, 30–40 seconds head movement, 40–45 seconds out of view, and 45–90 seconds steady recovery.

## Measurements and interpretation

- `stats.usable_fraction`, `tracking_fraction`, and `stable_at` describe accepted periodic samples, single-face tracking coverage, and time to the first accepted sample from the first submitted frame. Missing signal and startup remain in the denominator; `stable_at: null` means no accepted window.
- `samples[].fps` and `stats.mean_fps` measure processed capture-timestamp cadence. They are not isolated model throughput. `samples[].processing_ms` measures the estimator's frame-processing call; `inference_lag_ms` measures completed model-timeline lag behind that input frame, or null when no model output exists. Neither includes browser encoding or network delivery.
- `capture_diagnostics` is attached by the browser to camera/recording reports and survives later AI report updates. It includes initialization time, preview resolution, reported camera-track rate, observed callback/submission cadence, submitted/acknowledged frame counts, ACK round trips, sample frame age, and the maximum sample arrival gap. Simulation does not receive browser camera diagnostics.
- Callback cadence counts observed distinct video callbacks, so skipped callbacks are not counted as captured frames. Submission cadence counts actual WebSocket sends. Track settings are device-reported settings, not an independent count of exposed sensor frames.
- ACK round trip runs from send to receipt and includes transport, server queueing and processing. Sample frame age runs from the corresponding browser video callback to receipt, matching the server's rounded relative timestamp before its ACK. It includes encoding and delivery; it excludes sensor exposure/compositor delay and the older physiological window represented by the estimate. `sample_age_observations` is its denominator; no matches leave age unavailable. Maximum sample gap uses consecutive accepted-in-order sample arrivals, excluding setup and finish.
- Tracking coverage does not establish identity continuity. SQI, accepted-signal fraction, and recovery do not establish physiological accuracy or causal coaching benefit. There is no synchronized reference device in this procedure.

## Fixes and regression scope

The browser now invalidates the displayed BPM on a single-face tracking failure arriving between periodic samples. Returning to view does not restore an old BPM; a new accepted measurement sample is required. A camera stream granted after Finish is stopped immediately instead of remaining active. The estimator's deterministic rejection thresholds are unchanged.

Browser regressions cover between-sample face loss/recovery, delayed permission after Finish, capture/ACK/sample stalls, permission denial, and three generated-camera export/restart cycles including asynchronous report replacement. Backend checks cover finish/disconnect/error slot release and actual-checkpoint restart separately. These regressions validate software behavior, not the physical-camera exit criterion.

## Physical-camera record

Hardware: MacBook Pro (Mac17,9), Apple M5 Pro, 48 GB RAM, macOS 27.2; local Chrome; 640 × 480 camera preview with a reported 30 fps track. Frames submitted to FacePhys are downscaled to 320 × 240. Backend agent mode is `off`, session coaching is `rules`, and no metrics are sent to Muse. No reference device was used. The frontend runs in development mode; automated tests/build activity overlapped the first baseline, so these results are not a controlled throughput comparison.

| Run | Declared condition | Duration | Samples | Usable fraction | Single-face tracking | First stable signal | Mean processed capture |
|---|---|---|---|---|---|---|---|
| 1 | Stable baseline, confirmed by participant | 90.010 s | 181 | 29.83% | 100% | 20.502 s | 29.8 fps |
| 2 | Participant-selected dim room lighting throughout | 90.027 s | 181 | 9.39% | 99.45% | 35.521 s | 29.8 fps |
| 3 | Motion, face absence, recovery | 90.027 s | 181 | 32.60% | 95.58% | 12.018 s | 29.8 fps |

Run 1 exported successfully, with 2,699 / 2,699 frames acknowledged. Callback/submission cadence was 29.97 fps; mean/max ACK round trip 13.23/36.40 ms; mean/max sample frame age 20.83/31.40 ms across 181 matched observations; maximum sample arrival gap 510.20 ms. Mean estimator processing time was 4.14 ms; maximum observed inference timeline lag was 0 ms. Initialization took 11.64 seconds. After the report, the UI showed camera off and health reported `busy: false`. Returning to setup did not restart the backend.

Run 2 exported successfully, with 2,701 / 2,701 frames acknowledged. Callback/submission cadence was 29.99 fps; mean/max ACK round trip 10.82/19.70 ms; mean/max sample frame age 18.52/24.30 ms across 181 matches; maximum sample arrival gap 519.90 ms. Mean estimator processing time was 3.59 ms; maximum observed inference timeline lag was 0 ms. Initialization took 24.30 ms. Camera release and `busy: false` were confirmed again before setting up run 3.

The participant requested dim room lighting for run 2, but mean face-region pixel brightness increased from 78.59 in run 1 to 91.94 in run 2 (0–255 scale). No visible-face sample in run 2 crossed the fixed `<55` darkness threshold. Room illuminance and camera exposure were not independently measured; this is a participant-declared lighting condition, not verified low-light sensor degradation. The lower usable fraction cannot be attributed causally to lighting. Rules coaching continued, so this is also not a passive-policy comparison.

Run 3 exported successfully, with 2,701 / 2,701 frames acknowledged. Callback/submission cadence was 29.99 fps; mean/max ACK round trip 10.80/20.20 ms; mean/max sample frame age 18.69/25.40 ms across 181 matches; maximum sample arrival gap 523.30 ms. Mean estimator processing time was 3.56 ms; maximum observed inference timeline lag was 33.3 ms. Initialization took 30.30 ms. Camera release and `busy: false` were confirmed after the final export. All three reports were parsed using the strict backend `Report` schema, including their browser diagnostics, and retained outside the repository in Downloads.

Startup logged duplicate AVF receiver classes from OpenCV's and PyAV's bundled libavdevice libraries. No crash or transport failure occurred in this batch; the dependency warning was not resolved by these lifecycle changes. The private `pulsepilot-p4-summary.json` in Downloads records export hashes, reconciled metrics, and phase counts without copying raw participant reports into the repository.

Only after all three sessions, exports, and slot-release checks completed, the test backend was stopped and relaunched with its existing `.env` configuration (`assist`, AI configured) for normal use. No configuration file or credential was changed.

The third run's exported samples reconcile with the planned intervals:

| Capture interval | Samples | Single-face samples | Accepted BPM samples | Observation |
|---|---|---|---|---|
| 0–30 s, stable setup | 60 | 59 | 28 | First accepted signal at 12.018 s; startup remains included |
| 30–40 s, motion | 20 | 20 | 0 | Maximum motion proxy 0.578, above the unchanged 0.28 gate |
| 40–45 s, face absence | 10 | 3 | 0 | Seven absent-face samples from 41.521–44.522 s; every absent-face sample has null BPM |
| 45 s–finish, recovery | 91 | 91 | 31 | First accepted signal after returning at 58.023 s; acceptance remained intermittent |

UI observations confirmed accepted signal before the motion interval, withheld BPM during degradation, attention/tracking reacquisition, and completion. Because BPM was already withheld before the deliberate face absence, this physical run does not independently time removal of a previously accepted BPM; the between-sample browser regression verifies that specific case. There were no failed physical sessions or backend restarts in this batch. The low usable fractions are retained honestly; thresholds were not changed. This is one participant and one machine, with no reference accuracy or multi-user benefit claim.

## Executed software checks

| Check | Result | Scope |
|---|---|---|
| Full backend suite after changes | 187 passed, 2 skipped in 66.81 s | Existing sensing, protocol, orchestration, reports, new processing/lag diagnostics; two checkpoint tests remain opt-in |
| Freshness browser suite | 11 passed in 1.4 minutes | Existing capture/ACK/sample stalls, restart, denial, heatmap/waveform, immediate face-loss invalidation and delayed permission cleanup |
| Additional generated-camera export regression | 1 passed in 2.8 s | Three fixture sessions, locally attached diagnostics, asynchronous report replacement, export, camera release and restart |
| TypeScript, production build, Ruff, whitespace check | Passed | Static/build checks; build does not establish hosted deployment |

These checks and the three physical runs establish the local capture/report/restart flow. The manual runs do not validate the darkness threshold, physiological accuracy, general camera compatibility, human benefit, or controlled throughput-regression targets. P5 presentation and P6 evaluation remain separate work.
