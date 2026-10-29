# Verification record

## P2 LangGraph verification

October 27, 2026. [langgraph-p2.md](langgraph-p2.md) is the implementation/readiness reference; [p2-evaluation.json](p2-evaluation.json) and [p2-live-verification.json](p2-live-verification.json) contain the labeled raw evaluation records.

| Executed check | Result | Actual scope |
|---|---|---|
| Baseline `uv run pytest -q` | 101 passed, 2 skipped | P1 before P2 changes |
| Final `uv run pytest -q` | 165 passed, 2 skipped | Graphs, contracts, adversarial outputs, four modes, consent, task cleanup, frame ACK continuity, adaptive policy, telemetry/export/evaluation, existing sensing/protocol/report tests |
| `uv run ruff check pulsepilot tests ../scripts` | Passed | Python static checks |
| `uv sync` | Passed | Python 3.12 environment and updated lock; LangGraph 1.2.18 |
| `pnpm install`, `pnpm check`, `pnpm build` | Passed | Existing frontend dependencies, TypeScript, production build |
| `PULSEPILOT_TEST_URL=http://127.0.0.1:3002 pnpm test:e2e` | 22 passed in 1.8 minutes | Production frontend and credential-disabled backend on separate test ports; simulation, generated-camera/recording frames through FacePhys, consent, provenance, async report lifecycle, restart, freshness, mobile layout |
| Focused browser simulation/export after telemetry export changes | 1 passed in 23.8 seconds | Restarted backend with final report metadata; numerical report, JSON export, history, and measurement cleanup |
| `RUN_FACEPHYS_INTEGRATION=1 uv run pytest -q tests/test_facephys_integration.py` | 2 passed in 21.51 seconds | Actual checkpoint with synthetic frames, temporal heatmap state, WebSocket finish/restart and resource release |
| `uv run python ../scripts/smoke_facephys.py` | Passed | 360 finite BVP outputs; 797.9 model steps/second after 9.4-second warmup; blank frames yielded no accepted BPM |
| `uv run python ../scripts/evaluate_p2.py --output ../docs/p2-evaluation.json` | Nine trials completed | Local fixture policies, seeded identical traces through ReliabilityGate, randomized A/B/C order; no remote requests |
| `uv run python ../scripts/verify_sensing_agent.py --live --output ../docs/p2-live-verification.json` | Completed | Three real Meta requests carrying synthetic metrics only; two coaching deadline fallbacks, then validated report |
| `docker compose config --quiet` | Passed | Compose syntax/configuration, including agent mode propagation |
| Docker image build/run | Blocked | Docker daemon unavailable; images were not built/run |

The first browser run found an assertion using the previous report attribution text; it was updated. An overlapping targeted run also collided with Playwright's shared artifact directory. The final full browser run was sequential and all 22 tests passed. Test servers used ports 3002/8002 and an explicitly empty model key; existing user services on 3000/8000 were preserved.

The live coaching calls exceeded the 1.5-second deadline and used deterministic actions. Measured outcomes reached the next request. The live report schema and canonical claim references validated in approximately 3.65 seconds with 1,868 input and 478 output tokens reported by Meta. No timely live adaptive selection or human response benefit is claimed. The nine fixture trials show mean SQI about 0.469, usable fraction about 0.322, and first stable signal at 41 seconds in every condition. Quality is scripted independently of instructions; matching metrics and different action order establish policy wiring only.

P2 Core (M1–M4): verified in this automated/local scope. P2 Extended (M5): implemented and fixture-verified; partially empirically verified. Physical human-camera performance, reference-device accuracy, real-user counterbalanced benefit, controlled less-than-five-percent inference-throughput regression, Docker runtime, and durable hosting remain unverified. Synthetic/model-only throughput must not be read as end-to-end camera performance or accuracy.

## P3 live-decision verification — October 28, 2026

P3 meets its declared live-provider target over synthetic metrics. Implementation, methodology and limitations are documented in [P3 live decisions](p3-live-decisions.md).

| Check | Observed result | Scope |
|---|---|---|
| Fresh request under the previous 1.5-second deadline | Timeout with rules fallback | Confirms that the original budget remained impractical for this observed request |
| `uv run python ../scripts/verify_sensing_agent.py --live --trials 20 --output ../docs/p3-live-verification.json` | 20/20 validated selections and actual Muse commitments; zero abstentions, invalid responses, timeouts or unavailable results | Ten synthetic session pairs; later accepted requests received previous outcomes; end-to-end mean 2.131 seconds, maximum 3.008 seconds under a six-second budget |
| Additional live WebSocket loop with patched synthetic darkness/motion | 68 samples, two completed Muse-selected interventions, accepted outcome feedback, validated Muse report | Full application dispatch, coach commitment, event provenance and report path; [saved evidence](p3-websocket-verification.json) |
| Full backend suite | 181 passed, 2 skipped in 64.78 seconds | Delayed selection, stale/resolved conditions, face loss between samples, sample gaps, frame ACK continuity, consent/modes, cancellation, client reuse/cleanup, existing estimator/report contracts |
| Subsequent focused graph and batch-harness checks | 11 passed | Network timeouts classified separately; selected/abstained/invalid/obsolete results distinguished from actual commitments; small diagnostic batches cannot meet P3 |
| Ruff | Passed | Backend, tests and scripts |
| TypeScript and production build | Passed | Playback-rate state, waveform clock and pending copy |
| Focused production-browser suite | 9 passed in 26.0 seconds | Consent/preferences, 1× adaptive pending state, provenance, assisted explanations, disabled mode, asynchronous report lifecycle, 4× ordinary simulation/export/history |

Real calls used the existing ignored backend credential and `muse-spark-1.3`. The twenty-opportunity batch is preserved in [p3-live-verification.json](p3-live-verification.json), including every opportunity and its timing, category, provider response receipt, usage, previous outcomes and committed intervention. Timeout durations are censored; canceled requests do not reveal completed provider latency or billing. No live abstentions or failure cases occurred in the batch; automated tests cover those paths. This is one observed integration batch, not a guarantee about future provider reliability.

P4 physical-camera sessions, reference-device accuracy, human benefit, controlled throughput comparisons, Docker runtime and durable deployment remain unverified.
