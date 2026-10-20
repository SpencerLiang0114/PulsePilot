# Agents and closed-loop feedback

## Verified Meta interface

Meta lists `muse-spark-1.3` through its [Model API](https://dev.meta.ai/docs/models). Use server-only `MODEL_API_KEY` and `https://api.meta.ai/v1/chat/completions`. The [structured-output cookbook](https://dev.meta.ai/docs/cookbook/structured-output) documents `response_format: {type: "json_schema", json_schema: {name, strict, schema}}`. Pydantic validates responses again; reject unknown fields, invalid evidence identifiers, and instructions outside the deterministic eligible set.

The user explicitly requested Python orchestration and Meta models. Use documented HTTPS requests from Python rather than introducing a second TypeScript agent backend. Marketplace discovery for “muse” returned no integrations. Credentials are not presently available; do not describe a configured client as a tested live integration.

## MeasurementCoach

Deterministic tools derive camera conditions and a ranked list of eligible actions. Priority: visible single face → framing/distance → orientation → illumination → motion → cadence → signal. Muse may choose among eligible corrections and provide a short explanation, but cannot invent a measurement, override validity, or give medical advice.

Require the same dominant issue to persist for five seconds, then take that pre-intervention baseline, give the user three seconds to respond, and collect a disjoint five-second post window. Do not issue another instruction while measuring the outcome. Require sufficient matched sample coverage in both windows. Store mean SQI, usable proportion, and timestamps; camera metrics remain in the associated samples. Outcome labels use a change of at least eight SQI percentage points, never a claim of accuracy or causation. The report also preserves before/after usable proportions. Missing signal gives an inconclusive outcome. Apply an eight-second cooldown before repeating.

Use separate enter/exit quality thresholds for stable state. Immediately hide HR when face/cadence validity fails. No intervention when no important issue exists.

Meta calls have bounded timeouts and run without blocking acquisition. Use deterministic text immediately; apply a returned explanation only if its intervention is still active. A failed request is recorded as unavailable, with no fabricated AI provenance.

## ReportAnalyst

The server computes accepted-HR mean, median, range, trend points, observed duration, valid proportion, tracking continuity, camera-condition summaries, time to stable signal, cadence, latency, and intervention comparisons. Numerical data and conclusions remain immutable.

Send only those summaries to Muse. Require four structured sections: heart-rate interpretation, quality interpretation, intervention interpretation, and recommendations. Each statement references a server-generated evidence ID and declares fact, possible explanation, or limitation. Reject unknown IDs and medical/accuracy claims; fall back to deterministic analysis. UI always renders numerical statistics from server tools rather than model prose.

## SAM decision

[SAM 3.1](https://dev.meta.ai/docs/sam/overview) supports text-prompt image/video segmentation via `POST /v1/responses`, with streaming boxes/masks. Access requires a Meta API key; segmentation is not a face-pose or rPPG-quality API. Its latency, expense, extra facial-image transfer, and uncertain skin-mask benefit do not justify inclusion in the first slice. Existing six-point detector landmarks support approximate alignment and visibility now. Dense landmarks are a later upgrade.

Optional experiment: with explicit image-transfer consent, compare SAM skin/occlusion visibility against lightweight landmarks on annotated clips. Measure detection correctness, latency, and downstream usability. Never change the FacePhys crop/mask without an independent ablation and reference validation.
