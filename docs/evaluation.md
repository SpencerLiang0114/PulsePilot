# Evaluation protocol

Compare passive FacePhys, deterministic coaching, and Muse-assisted coaching with identical weights, capture settings, thresholds, session length, and signal processing. Counterbalance order and use repeated sessions under stable light, backlighting, motion, misalignment, and partial occlusion. Record actual interventions and their timing. Do not claim that replay simulates a person's response to live advice.

## Metrics

- Usable proportion: accepted fixed-interval measurement samples / all measurement samples, including startup and missing signal.
- Mean periodicity SQI: finite observed SQI; disclose missing proportion.
- Time to first stable window: capture timestamp relative to first accepted frame, null if never stable.
- Intervention count and outcome: post-window SQI minus disjoint pre-window SQI, usability change, and inconclusive count.
- Face tracking: fraction of observation samples with a visible face; not an identity-continuity guarantee.
- Heart-rate variability in the estimates: SD and range of accepted HR; not physiological HRV or an accuracy score.
- Latency: inference snapshot processing time and server lag; network latency requires browser measurements.
- Reference MAE: align by timestamp to a synchronized reference device and compare matched valid windows; disclose exclusions. Without reference data, omit MAE entirely.

## Reproducibility

The website accepts a local recording and streams it through the same estimator without persisting it. The command-line replay evaluator accepts a video path and emits numerical windows and a report. Capture timestamps must derive from the video's timeline.

Synthetic quality scenarios exercise poor lighting, motion, recovery, cooldown, and report generation without camera/model requirements. Every result carries `mode=simulation`, and synthetic numbers are clearly labeled throughout the interface and export. They validate software behavior only.

## Limitations

Thresholds are provisional, not validated population-wide. Landmark-derived pose and visibility are approximations; glasses/skin masks are not comprehensively detected. Low-rate or irregular capture is rejected even if upstream interpolation produces a high SQI. Compression, lighting, skin tone, cameras, and motion can affect performance. Better SQI and lower estimated-HR variance do not establish better accuracy.

No clinical evaluation, reference-device MAE, or end-to-end public deployment is claimed until separately executed and documented.
