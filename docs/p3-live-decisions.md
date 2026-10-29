# P3 — Reliable live Meta decisions

Implemented and verified October 28, 2026 (Eastern). P3 meets the roadmap's declared synthetic live-provider target. This does not establish physical-camera reliability, human benefit, or heart-rate accuracy.

## Changes

- Adaptive selection has a six-second application budget, including graph compilation, provider transfer, validation and service execution. Explanation/observation graphs retain 1.5 seconds; optional reports retain twelve seconds. The provider's independent ten-second invocation and twelve-second HTTP/four-second connect limits remain bounded by those application budgets.
- Each session lazily creates one HTTP client after consent/configuration checks and reuses it for coaching and reporting. Finish cancels/drains coaching while preserving the client for report analysis. Disconnect/close cancels/drains all work and closes the owned client. Injected test providers remain caller-owned.
- Wire payloads omit redundant JSON whitespace and schema titles. Required fields, strict schemas, identity binding, supported explanations and canonical validation are preserved.
- Capture freshness is independent of planning: a gap exceeding 1.5 seconds still invalidates context. Current eligibility, safety, proposal identity and remaining observation time are rechecked at commitment. Material changes in an offered action's triggering metrics discard pending context, using the same tolerances as outcome-memory retry eligibility. Resolved selected actions cannot commit. At six capture seconds, a still-eligible pending action uses rules timeout fallback; late output cannot replace it.
- Face/cadence corrections keep their deterministic path. Other modes and session consent boundaries remain authoritative. Frame processing, samples and ACKs continue independently of provider work.
- Adaptive simulation runs at 1× with consent and a configured provider so capture time and the wall-clock budget agree. Other simulations retain 4× playback. The `ready.playback_rate` value drives the banner and waveform clock. The pending message explicitly says measurement continues.
- HTTP response receipt is counted separately from validation. The verification script records provider outcomes separately from actual coach commitments and applied abstentions. Timeout elapsed values are censored durations, not completed provider latencies.

## Declared batch and result

The batch was declared as twenty eligible opportunities, grouped into ten independent sessions with two sequential opportunities each. Initial candidates included persistent darkness and motion. Each later request received the same coach's completed before/after outcome, with unsuccessful actions suppressed under unchanged conditions. SQI was held constant at 0.3; outcomes therefore establish policy wiring, not improvement.

While a request was pending, synthetic samples continued at approximately two per wall-clock second. Outcome collection and cooldown were advanced synthetically between requests to avoid spending API time on idle windows. Selection, validation and commitment used the real service and coach. The full records include failures, categories, usage, candidate sets, previous outcomes, per-request timing and committed interventions in [p3-live-verification.json](p3-live-verification.json).

| Measurement | Result |
|---|---:|
| Eligible opportunities | 20 |
| Validated selections within six seconds | 20 (100%) |
| Valid abstentions | 0 |
| Invalid responses / timeouts / unavailable | 0 / 0 / 0 |
| HTTP responses received | 20 |
| Actual Muse-selected commitments | 20 |
| Mean end-to-end time through the next sample/commitment | 2.131 seconds |
| Maximum end-to-end time | 3.008 seconds |
| Later accepted decision received prior measured outcomes | Yes |
| Total batch elapsed | 42.66 seconds |

The target was at least 90% validated outcomes within budget, at least twenty opportunities, repeated actual Muse commitments, and a later accepted decision receiving history. This batch passed. It observed no live abstentions or failure responses; those paths are exercised by automated regression tests. The model was `muse-spark-1.3`. Meta reported 16,796 input and 8,089 output tokens across the batch; no monetary cost is inferred.

A fresh pre-change diagnostic also exceeded the original 1.5-second budget. Reuse and payload trimming were implemented together with the longer deadline; this is not an isolated benchmark attributing latency savings to either optimization.

## Application verification

An additional live WebSocket session used the application's full dispatch/commitment/report path with synthetic metrics at real time. It delivered 68 samples, committed two Muse-selected instructions, sent the first completed outcome into the next accepted decision, and returned a validated Muse report after the numerical report. Event IDs and graph provenance were preserved. Full evidence: [p3-websocket-verification.json](p3-websocket-verification.json). No physical camera was used.

Regression coverage includes delayed valid output beyond the former deadline, capture expiry, material context changes, resolved issues, face loss between sample events, sample gaps, insufficient remaining time, consent/mode restrictions, finish/disconnect cancellation, uninterrupted camera-frame ACKs, strict response contracts, abstention, fallback attribution, HTTP client reuse and cleanup, and invalid-response accounting.

Run the batch explicitly; it makes real billable provider requests using only synthetic metrics:

```sh
cd backend
uv run python ../scripts/verify_sensing_agent.py --live --trials 20 --output ../docs/p3-live-verification.json
```

Without `--live`, the script refuses remote calls. Fewer than twenty trials can diagnose access/latency but cannot satisfy the P3 criterion. A missed target exits nonzero after writing the complete normal batch result. Credentials remain in ignored `backend/.env` or the server environment.

See [verification.md](verification.md) for automated check results. P4 real-camera sessions, reference-device accuracy, human benefit, controlled inference throughput comparisons and durable deployment remain unverified. This result applies to the observed batch, not a reliability guarantee for future provider traffic.
