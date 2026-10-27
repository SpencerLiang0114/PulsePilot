# Evaluation protocol

P2 compares **A: deterministic rules**, **B: rules-selected actions with Muse explanations/report selection**, and **C: LangGraph adaptive pre-commit selection**. Use `AGENT_MODE=off`, `assist`, and `adaptive` respectively, `coaching=meta`, and explicit AI consent for B/C. Passive FacePhys is an optional additional ablation. Keep weights, capture settings, thresholds, session length, and signal processing identical. Counterbalance order and repeat sessions under stable light, backlighting, motion, misalignment, and partial occlusion. Record actual interventions and timing. Replays do not simulate a person's response to advice.

The reproducible fixture harness is `cd backend && uv run python ../scripts/evaluate_p2.py --seed 27 --repetitions 3 --output ../docs/p2-evaluation.json`. It randomizes A/B/C order while sharing each seeded trace through ReliabilityGate, uses no remote model, and records its synthetic source and resource scope. The saved nine-trial run has identical mean SQI (~0.469) and usability (~0.322) across policies because quality is scripted independently of actions. Different action sequences verify policy wiring, not benefit. `--reports A.json B.json C.json` summarizes actual exported reports and safe run telemetry while retaining source labels. Optional input/output token-price arguments produce estimates from observed usage with explicit price assumptions. See [the P2 guide](langgraph-p2.md) for live-provider evidence and limitations.

## Metrics

- Usable proportion: accepted fixed-interval measurement samples / all measurement samples, including startup and missing signal.
- Mean periodicity SQI: finite observed SQI; disclose missing proportion.
- Time to first stable window: capture timestamp relative to first accepted frame, null if never stable.
- Intervention count and outcome: post-window SQI minus disjoint pre-window SQI, usability change, and inconclusive count.
- Intervention completion rate: instructions with the full three-second response plus five-second observation interval / all committed instructions. Early-finished inconclusive comparisons remain in the outcome distribution without counting as completed intervals.
- Face tracking: fraction of observation samples with a visible face; not an identity-continuity guarantee.
- Heart-rate variability in the estimates: SD and range of accepted HR; not physiological HRV or an accuracy score.
- Latency: inference snapshot processing time and server lag; network latency requires browser measurements.
- Agent metrics: accepted/rejected proposals, fallback frequency, graph/model latency, and token/request usage when supplied by Meta. Missing usage or price inputs leave API cost unavailable, especially for canceled calls.
- Resources: policy CPU/wall time and peak traced Python allocations are measured by the fixture harness. Its execution rate is not camera or FacePhys throughput. Record synchronized capture/inference throughput and process memory separately for controlled hardware comparisons; the less-than-five-percent throughput-regression target has not been established by this fixture run.
- Reference MAE: align by timestamp to a synchronized reference device and compare matched valid windows; disclose exclusions. Without reference data, omit MAE entirely.

## Reproducibility

The website accepts a local recording and streams it through the same estimator without persisting it. The command-line replay evaluator accepts a video path and emits numerical windows and a report. Capture timestamps must derive from the video's timeline.

Synthetic quality scenarios exercise poor lighting, motion, recovery, cooldown, and report generation without camera/model requirements. Every result carries `mode=simulation`, and synthetic numbers are clearly labeled throughout the interface and export. They validate software behavior only.

## Limitations

Thresholds are provisional, not validated population-wide. Landmark-derived pose and visibility are approximations; glasses/skin masks are not comprehensively detected. Low-rate or irregular capture is rejected even if upstream interpolation produces a high SQI. Compression, lighting, skin tone, cameras, and motion can affect performance. Better SQI and lower estimated-HR variance do not establish better accuracy.

No clinical evaluation, reference-device MAE, or end-to-end public deployment is claimed until separately executed and documented.
