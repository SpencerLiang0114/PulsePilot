# Verification record

## P2 LangGraph verification

October 27, 2026. [langgraph-p2.md](langgraph-p2.md) is the implementation/readiness reference; [p2-evaluation.json](p2-evaluation.json) and [p2-live-verification.json](p2-live-verification.json) contain the labeled raw evaluation records. The older sections below retain their original historical scope.

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

October 20, 2026. These are executed checks, not a claim that every MVP acceptance gate has been met.

For the subsequent agentic sensing implementation, authenticated Meta requests and current test results, see [P1 validation](p1-verification.md). The dated checks below are retained as historical records.

## Passed

| Check | Result | What it establishes |
|---|---|---|
| Audited upstream commit | `4d24237e7b14e17429b49d0334f2282b7d2fd159` | Actual FacePhys API, checkpoint presence, timing, and source/model licensing distinction |
| `uv sync --python 3.12` | Passed, locked environment | Local dependencies resolve and install |
| `scripts/smoke_facephys.py` | 360 finite BVP outputs from the frozen checkpoint | Real JAX/Keras model execution on synthetic input |
| Initial CPU smoke | 26.19 s warmup; 795.7 model-only fps | This machine's initial model-only throughput, excluding full capture/network/detection overhead |
| Blank RGB frame ingestion | BPM `null`, “Adjust your position” | No physiological estimate displayed for a missing face |
| Upstream HR/SQI numerical check | A synthetic 1.2 Hz sinusoid yielded 72 BPM; SQI 0.9167 | Signal-processing code executes under the pinned SciPy stack; no human accuracy claim |
| Backend tests | 32 passed | Quality validity/hysteresis, reset after multiple faces, disjoint intervention windows, cooldown, missing-data reports, evidence IDs, mocked Meta schema/timeouts, origins, consent, PNG limits, and session cleanup |
| TypeScript and production build | Passed | Website compiles with installed Next.js 16.4.2 and React 19.3.1 |
| Ruff | Passed | Python static checks |
| Browser tests through public HTTPS URL | 8 passed | Simulation/report/export/history; recording replay/end-of-file; consent; mobile/navigation; unavailable service; synthetic camera → PNG → WSS → real FacePhys → report and stopped tracks; late/cancelled AI report lifecycle with mocked responses |
| CLI recorded-video replay | 12 observation windows from a six-second synthetic recording | Real file decode/adapter/report path; no real face or accepted HR |
| Visual inspection | Desktop, mobile, and report screenshots inspected | Font rendering, layout, mobile overflow, and source labeling |
| Docker Compose configuration | Parsed successfully | Compose syntax only |

Browser tests ran at `https://painting-everybody-richardson-cape.trycloudflare.com`, with production Next.js on loopback port 3001 proxying Python on port 8000. The public health endpoint and secure WebSocket path were both exercised. Cloudflared 2026.10.2 was downloaded from its official GitHub release and verified against the release's SHA-256 asset digest.

The replay and camera browser fixtures contain generated flat-color frames. They prove transport and failure gating, not facial pulse recovery. Simulation reports carry `mode=simulation` and never stand in for real inference.

## Task 1: stale-data invalidation

Implemented and checked October 20, 2026. Before the fix, the new frozen-capture regression failed because `72 BPM` remained visible after 5.5 seconds despite stopped capture and an open socket.

The session watchdog now checks every 250 ms for five seconds without advancing capture, transport ACKs, or advancing sample timestamps. A stale session hides BPM, leaves the stable state, stops camera tracks, closes the socket, and offers “Try again.” Simulation checks sample freshness without requiring camera frames or ACKs. The watchdog is cleared on finish, cancel/restart, failure, report, socket close, and unmount.

| Check | Result | Scope |
|---|---|---|
| `pnpm test:e2e tests/freshness.spec.ts` | 4 passed | Local development frontend, mocked open sockets, synthetic canvas camera: frozen capture despite ongoing ACKs/samples; missing samples despite ACKs/capture; repeated sample timestamps; missing ACKs despite samples. Each case verifies BPM removal within 5.5 seconds, stopped tracks, recovery, a healthy restart lasting six seconds, and no false timeout during slow report preparation. |
| `pnpm check` and `pnpm build` | Passed | TypeScript and production frontend build |
| `pnpm test:e2e tests/experience.spec.ts tests/async-report.spec.ts` | 8 passed in 43.7 seconds | Local production frontend and real backend with Meta credentials disabled. Includes accelerated simulation, recording end-of-file, synthetic-camera FacePhys transport/cleanup, and mocked asynchronous report lifecycle. |

These checks establish browser freshness behavior and preserve the existing synthetic-input integration coverage; they do not establish physical-camera or physiological accuracy.

## FacePhys backend service lifecycle

Implemented and checked October 20, 2026. The existing real-time service now validates capture timestamps before decoding, checks the PNG IHDR header, and validates control messages against a strict schema. Model startup failure closes partially initialized workers; cancellation waits for outstanding model work before closing resources and releasing capacity. Failed model startup or runtime failure clears the previous readiness status, and a successful retry clears the error.

| Check | Result | Scope |
|---|---|---|
| `cd backend && RUN_FACEPHYS_INTEGRATION=1 uv run pytest -q` | 51 passed in 21.26 seconds | Includes 50 deterministic tests and one opt-in real-checkpoint integration test. New cases cover startup cleanup, duplicate startup, cancellation during initialization, busy capacity, finish/restart, disconnect, idle timeout, malformed frames/commands, duplicate timestamps, wall-clock termination, and readiness recovery. |
| Real-checkpoint integration case | Passed | 330 generated PNG frames paced at nominal 30 Hz through the FastAPI WebSocket handler, numerical report, model cleanup, and a fresh recording session. The final camera sample reported 30 fps; blank frames produced no accepted BPM. |
| `uv run python ../scripts/smoke_facephys.py` | Passed | 360 finite BVP samples; 9.57-second warmup and 675.7 model-only fps on this Mac during this run. These timings exclude browser/network overhead and are not an end-to-end performance guarantee. |
| `pnpm test:e2e tests/experience.spec.ts --grep 'recording runs\|real FacePhys'` | 2 passed in 18.6 seconds | Existing local development frontend on port 3000 and updated Python service on port 8000; synthetic browser camera and generated recording, report completion, and camera-track shutdown. Meta credentials were disabled for this run. |
| `uv run ruff check pulsepilot tests ../scripts` | Passed | Python static checks |

The default `uv run pytest -q` skips the opt-in checkpoint test. Upstream flat-signal normalization and the existing TestClient deprecation warnings remain; invalid model output is excluded from the accepted estimate.

Run instructions, health semantics, payload limits, and client message shapes are in the [backend service guide](backend-service.md). This verification uses generated input and establishes execution, transport, and cleanup, not physiological accuracy or permanent deployment.

## Camera detection crash and live preview

Checked October 20, 2026. FacePhys returns `(box, landmarks, score)`, but the adapter unpacked `(box, score, landmarks)`. The first detected face therefore raised `cannot reshape array of size 1 into shape (2)` and closed the camera session. Corrected fixtures reproduced this exact error before the fix. The adapter now uses the upstream order and extracts its one-element confidence array explicitly.

- Backend: 51 unit/protocol tests passed; the opt-in real-checkpoint WebSocket integration also passed. Focused Ruff checks, TypeScript, and the production build passed.
- Browser: all 14 cases passed across the suite run and a focused rerun after correcting an ambiguous alert selector in the new permission test. Coverage includes visible video, face-box removal after face loss, permission-denied recovery, stale-data cleanup, recording playback, and stopped tracks.
- Face-containing input: 20 frames derived transiently from the supplied reference screenshot passed through the real detector/estimator, returning six landmarks without a premature BPM. A separate browser canvas replay of that image exercised PNG/WebSocket transport, real face detection, preview/overlay alignment, fullscreen, report completion, and camera-track shutdown. This was static-image replay, not physical-camera capture or physiological validation.
- Desktop and mobile screenshots were inspected. The live preview now includes the heart-rate readout, tracking box, waveform, and remaining time; simulation retains its explicit synthetic labeling.

## Not verified / external dependencies

- **Human Muse session:** authenticated API requests, a synthetic action/outcome/adaptation loop, real timeout fallback and validated report interpretation now pass; see [P1 validation](p1-verification.md). A consenting human-camera session with Muse remains unverified.
- **Consenting-user heart rate:** no suitable human video or live physical-camera measurement was provided. A user still needs to complete this acceptance check.
- **Physiological accuracy:** no synchronized reference data, clinical testing, or accuracy across skin tones/cameras/lighting. Higher SQI and lower variance do not establish accuracy.
- **Permanent hosting:** the public URL is an active temporary tunnel to this Mac. It expires when the process stops and is unavailable if the Mac sleeps. Vercel authentication and persistent hosting are not provisioned.
- **Container execution:** Docker CLI/Compose are present, but the Docker daemon is not running; images were not built/run.
- **SAM:** evaluated from official API documentation and intentionally excluded. No additional value has yet been measured.
- **Checkpoint rights:** upstream explicitly distinguishes model licensing from MIT source licensing; FacePhys-specific redistribution/commercial terms were not established.

## Known runtime notes

macOS logs duplicate AVFoundation classes when PyAV and OpenCV load their bundled FFmpeg libraries. No crash occurred in the executed checks; Linux container behavior remains untested. The upstream normalizer warns on flat/no-face signals; PulsePilot suppresses invalid BPM. Starlette's TestClient emits an httpx deprecation warning, without test failures.

## Definition-of-done status

Website, capture/transport, real pretrained inference execution, deterministic sensing/guidance, closed-loop comparisons, session reports, simulation/replay, and a temporary HTTPS demonstration are integrated. P1 additionally verifies authenticated Muse action selection, outcome feedback, claim validation and fallbacks on synthetic conditions. Final MVP completion still requires a real consenting-user measurement and the chosen durable deployment. Reference-device validation remains a separate scientific evaluation.
