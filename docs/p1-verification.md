# P1 implementation validation

P1 implements proposal → asynchronous Muse selection → deterministic validation → instruction → measured outcome → session-local adaptation. The estimator, model weights, inference/capture cadence, reliability thresholds and measurement acceptance logic were preserved.

## Automated checks

| Check | Result |
|---|---|
| Backend suite | 101 passed; two opt-in real-checkpoint tests skipped in the default run |
| Opt-in real FacePhys checkpoint tests | Both passed |
| FacePhys smoke test | 360 finite BVP samples; blank-frame BPM remained null |
| Ruff, backend and scripts | Passed |
| TypeScript | Passed |
| Next.js production build | Passed |
| Playwright against production build and real local inference backend | All 20 passed |

The backend suite includes multiple persistent candidates, valid selection and abstention, malformed output, ineligible actions, unsupported explanations, authentication failure, timeout cancellation, deterministic fallback, late/stale result rejection, disjoint timing windows, cooldown, adaptation after unsuccessful outcomes, inconclusive evidence, consent, mode isolation, and finish/disconnect/restart cleanup. Report tests reject altered statistics, invented improvement, medical/accuracy/causal prose and invalid claim identities or sections, including when a real unsuccessful intervention is cited.

The browser suite includes mode selection, explicit consent, pending-versus-committed instructions, provenance and outcome timelines, report export/history, camera and recording transport through actual FacePhys, and all existing freshness/watchdog, heatmap and waveform checks. Browser camera sources are generated canvas streams, not people.

## Real Meta API validation

Authenticated `muse-spark-1.3` calls used the documented strict JSON-schema response format. An initial request without explicit minimal reasoning took 3.74 seconds. With minimal reasoning, the two-second deadline admitted real decisions and rejected slower ones as intended.

One live synthetic loop completed two Muse-selected interventions: motion at 13 seconds (evaluated at 21), then lighting at 36 seconds (evaluated at 44). Requests took 1,791 and 1,717 ms. Both observed outcomes were unchanged, and the second context included the first outcome. Camera-condition inputs were explicitly synthetic; SQI stayed at 0.3.

The latest [saved live run](p1-live-verification.json), after the report-claim classification correction, processed 89 samples through all five states. Muse selected motion in 1,723 ms. The next request hit the deadline at 2,002 ms and the deterministic fallback selected lighting, retaining the first measured outcome and recording `decision_source: "rules"`, `decision_status: "fallback_timeout"`. Both interventions completed without overlapping windows. The final report passed exact typed-claim validation and recorded `analyst: "muse"`.

Reproduce with:

```sh
cd backend
uv run python ../scripts/verify_sensing_agent.py --live --output ../docs/p1-live-verification.json
```

This command sends synthetic scalar metrics and bounded intervention history to Meta, including the optional report request. It sends no frames, facial geometry, or raw waveform. Latency and model decisions can vary; the deadline remains two seconds.

## Remaining validation limits

No consenting human-camera session or synchronized reference-device measurement was performed. The real model/checkpoint and browser paths are validated with synthetic inputs; physiological accuracy and actual user response to guidance remain unverified. No deployment was performed. Fireworks, Baseten and Modal are outside P1 and were not invoked.

The environment emits an existing Starlette/httpx deprecation notice. The standalone model smoke run also emitted upstream filtering warnings for its synthetic inputs and duplicate macOS AVFoundation class notices; it completed with finite model output and suppressed blank-frame BPM.
