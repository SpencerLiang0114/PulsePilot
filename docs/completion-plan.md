# Completion plan

Reviewed October 20, 2026 against commit `385e9ff` and the current working tree. This is the remaining-work sequence; [implementation-plan.md](implementation-plan.md) describes the original scope.

## Current status

PulsePilot has an integrated research MVP: Next.js measurement UI, camera/recording transport, frozen FacePhys execution, conservative BPM gating, deterministic coaching, before/after intervention records, four-section reports, in-memory history, JSON/print export, and optional Muse interpretation. Deployment configuration exists for a persistent backend and either a Vercel frontend or a container stack.

Checks executed during this review:

| Check | Result | Scope |
|---|---|---|
| `pnpm check` | Passed | TypeScript |
| `pnpm build` | Passed | Production frontend build |
| `cd backend && uv run pytest -q` | 32 passed | Backend numerical, protocol, and mocked-agent tests |
| `cd backend && uv run ruff check pulsepilot tests ../scripts` | Passed | Python static checks |
| `pnpm test:e2e` | 8 passed in 43.9 seconds | Local production frontend and real backend; synthetic camera/recording input; mocked asynchronous AI updates |
| Backend health after browser tests | Model ready, slot free | Installed checkpoint initialized and the tested sessions released capacity |
| Docker daemon | Unavailable | Container images were not built or run |

The browser run intentionally disabled Meta credentials. No real-person measurement, live Muse request, reference-device accuracy, or durable public deployment was established by this review. The earlier HTTPS tunnel results in [verification.md](verification.md) are historical evidence; that URL was not revalidated here.

Two additional probes reproduced gaps outside the passing suite:

- **Stale live estimate:** the timeout in `lib/use-measurement.ts` runs inside the video-frame callback. With a mocked open socket and a synthetic camera that stopped producing frames, the UI still displayed `72 BPM` and `Signal stable` after 8.5 seconds. The real backend has a separate fifteen-second idle timeout, but the browser does not independently invalidate the stale estimate when callbacks stop.
- **Unsupported AI narrative:** `backend/pulsepilot/agents.py` checks evidence-ID existence and selected text patterns, without ensuring that the narrative agrees with the evidence. A mocked analysis saying “The pulse remained steady throughout the session.” was accepted as Muse analysis for an empty session whose mean BPM was null.

Existing changes to `package.json`, `pnpm-lock.yaml`, and generated `next-env.d.ts` predate this review. No application fixes are included in this plan.

## Start external dependencies now

These can proceed while tasks 1–3 are implemented:

- Obtain the promised Meta API access for an authenticated integration check; keep credentials server-side.
- Arrange a consenting participant and physical camera for task 4. If reference accuracy is desired, arrange synchronized reference measurements for the separate evaluation below.
- Confirm the intended checkpoint use with its authors before a deployment that redistributes weights or requires unresolved model rights. Preserve the source/model licensing distinction already documented.
- Choose a durable hosting arrangement and provide the required account access for task 8. The current one-session-per-process design does not require accounts, a database, or multi-user scaling.

## Ordered tasks

### 1. Invalidate stale camera and measurement data

**Depends on:** none. **Scope:** `lib/use-measurement.ts`, focused browser regression tests.

**Status:** completed October 20, 2026. A session-scoped watchdog checks capture, ACK, and advancing sample freshness every 250 ms against a five-second limit. Four new browser regressions and all eight existing browser tests passed; see [verification.md](verification.md#task-1-stale-data-invalidation).

- Add a session-scoped freshness watchdog independent of video-frame callbacks. Distinguish capture progress, transport acknowledgements, and fresh measurement samples so ACK traffic alone cannot keep an old BPM valid.
- Hide BPM and leave the stable state when data become stale; provide a useful recovery action. Clean up the watchdog on finish, cancel, failure, restart, and unmount.
- Preserve recording end-of-file behavior and simulation timing.

**Done when:** a test first displays an accepted estimate, then freezes capture while leaving the socket open, and verifies that the estimate disappears within the defined freshness limit. Cover continuing ACKs without new samples, normal capture, and restart without a timer from the previous session affecting it.

### 2. Constrain AI conclusions to supported facts

**Depends on:** none. **Scope:** `backend/pulsepilot/agents.py`, schemas if necessary, and `backend/tests/test_agents.py`.

- Keep measurement facts and intervention outcomes deterministic. Use bounded, machine-checkable claim types or deterministic rendering for factual conclusions rather than expanding the prose blacklist.
- Reject claims about stable pulse when no accepted windows exist, unsupported improvement synonyms, invented observations, and coaching explanations that contradict the eligible action despite repeating the correct issue ID.
- Preserve all numerical results, evidence records, and deterministic fallback when interpretation fails.

**Done when:** regression tests reject the reproduced empty-session claim and contradictory coaching; supported interpretation still succeeds; failed interpretation cannot change statistics, measurements, or intervention outcomes.

### 3. Complete lifecycle coverage and automate the release checks

**Depends on:** tasks 1–2. **Scope:** backend/browser tests, `playwright.config.ts`, a minimal CI workflow, and check documentation.

- Add focused coverage for camera permission denial, track loss, cancel during initialization, rapid restart, busy inference capacity, mid-session disconnect, idle timeout, and maximum duration. Use controlled estimator fixtures for protocol timing cases.
- Assert that each terminal path stops capture, releases the model slot, hides stale BPM, and permits a subsequent session.
- Add CI for locked dependency installation, TypeScript/build, backend tests/Ruff, and deterministic browser scenarios. Give real-checkpoint integration tests a separate explicit job or documented command so a mocked run is never reported as real inference coverage.
- Review the existing dependency updates as a separate change; preserve them until their owner decides their delivery scope.

**Done when:** a clean checkout has a documented repeatable check path, CI runs the intended checks, and each added lifecycle scenario verifies cleanup and successful restart.

### 4. Validate a real-person session and measure full-pipeline performance

**Depends on:** tasks 1–3; consenting participant and camera. **Scope:** capture/estimator fixes only as measurements justify them; evaluation and verification records.

- Run a 60–90 second physical-camera session in steady light. Confirm face detection, accepted BPM windows, plausible waveform, report/export, and stopped camera tracks.
- Exercise face loss, motion, poor light, and recovery. Record when BPM is hidden and how much fresh data are required before it returns.
- Measure processed capture rate, dropped frames/backpressure, server processing lag, and browser-to-server timing. The gate requires at least 24 actual fps; target 30 fps. Model-only throughput is insufficient evidence.
- Repeat on the intended demo browser/device and test an ordinary network connection. Fix demonstrated bottlenecks and add regressions before changing provisional thresholds.

**Done when:** an actual face produces accepted windows under suitable conditions, invalid conditions suppress BPM, recovery works, and the end-to-end cadence/latency and failure results are recorded. Use aggregate metrics or consented artifacts; no raw participant video belongs in Git. This does not establish physiological accuracy.

### 5. Validate Muse Spark with authenticated requests

**Depends on:** task 2 and Meta credentials; use task 4 data for the final check. **Scope:** Python integration, agent tests, and verification record.

- Verify the configured model, request format, and strict output schemas with real API responses; adjust only incompatibilities demonstrated by those responses.
- Exercise an eligible coaching explanation and the final four-section report with explicit metrics-sharing consent.
- Confirm that opting out makes no Meta request, slow coaching never blocks acquisition, and authentication/quota/timeout/schema failures preserve deterministic results.
- Record provenance and useful failure categories without logging keys, raw video, or physiological request bodies.

**Done when:** one real session receives validated Muse coaching and report interpretation; its numerical results remain unchanged; consent and failure tests pass. A populated key or `ai_configured=true` alone is insufficient.

### 6. Run and document a small coaching comparison

**Depends on:** tasks 4–5 for the complete comparison. Passive versus rules can begin after task 4. **Scope:** [evaluation.md](evaluation.md), replay tooling only where needed, and aggregate results.

- Follow the existing protocol for passive FacePhys, deterministic coaching, and Muse-assisted coaching, keeping weights, settings, duration, and thresholds fixed and counterbalancing order.
- Record usable fraction, observed SQI and missingness, time to stable signal, intervention outcomes/inconclusive counts, cadence, and latency. Disclose participant/session counts and exclusions.
- Replay may compare processing behavior, but cannot establish how a person responds to live advice. Report negative or inconclusive outcomes as such.

**Done when:** a reproducible results table and method are saved, with claims limited to what the observations support. A small demonstration is not population validation or proof of causal benefit.

### 7. Build and exercise the container deployment

**Depends on:** task 3; checkpoint-use clarification before distributing an image containing weights. **Scope:** Dockerfiles, Compose/Caddy configuration, and deployment runbook.

- Start a Docker daemon and build both images from a clean context with locked dependencies.
- Run the stack through its single origin. Verify model initialization, PNG/WebSocket transport, simulation, recording, finish/disconnect cleanup, and restart behavior.
- Check build/runtime environment handling and secret exclusion. Confirm readiness and failure visibility for the model process; retain one Uvicorn worker and the single-session limit.

**Done when:** actual Linux containers run the application and browser integration checks pass through the proxy. Record startup time and resource use; successful Compose parsing alone does not complete this task.

### 8. Deploy the complete application to durable HTTPS hosting

**Depends on:** tasks 4–5 and 7, hosting access, and checkpoint-use clarification for the intended deployment. Task 6 can finish alongside deployment. **Scope:** the selected hosting configuration and [deployment.md](deployment.md).

- Use either the documented persistent container stack or Vercel frontend plus persistent inference host. Provision HTTPS/WSS, exact allowed origins, process restart, and server-only Meta credentials.
- If using Vercel, upgrade the installed CLI before deployment with `npm i -g vercel@latest`; the documented installed version is 53.2.0. Authenticate and configure the backend URL before building.
- Benchmark the hosted full pipeline, including initialization and network latency. Confirm that sessions meet the cadence gate, concurrent users get an actionable busy response, and disconnects release capacity.
- Run the browser suite against the public URL and complete a separate consenting-user session with Muse enabled.

**Done when:** the stable public URL completes camera → real FacePhys → coaching → numerical/Muse report without relying on the development Mac. Document the deployed revision, environment settings, restart/rollback procedure, and measured capacity.

### 9. Finish acceptance review and publish an accurate handoff

**Depends on:** tasks 1–8. **Scope:** final verification, README/runbooks, and release artifacts.

- Rerun release checks on the final revision and review desktop/mobile, keyboard setup/consent, errors, source labels, report evidence, print output, and JSON export.
- Update `docs/verification.md` with dates, commands, environment, and actual outcomes. Replace the temporary demo link with the verified durable URL and reconcile older status statements.
- Provide a short demo sequence covering normal measurement, one quality correction, report evidence, and a recoverable failure. Include known limits and operator recovery steps.
- Keep optional work out of this finish line: accounts, durable history, SAM, dense landmarks, HRV, model training, native apps, and multi-session scaling.

**Done when:** the documented MVP acceptance criteria are supported by final-revision evidence, the public demo is reproducible, and every remaining limitation is explicit.

## Separate scientific evaluation: reference-device accuracy

This is required before making accuracy claims, and is separate from completing the research MVP.

- Collect consented video and synchronized reference heart rate across the intended conditions and participants.
- Define alignment before reporting MAE. `scripts/replay.py` currently matches each emitted estimate to the nearest reference timestamp within 0.5 seconds, while the estimator uses a trailing signal window. Specify and test which reference interval that window should be compared with, including any offset, missingness, and exclusions.
- Report matched-window counts, coverage, MAE, and condition-specific limitations. Do not tune and evaluate thresholds on the same held-out sessions.

**Done when:** alignment has numerical tests and reproducible reference results exist. Until then, retain the explicit statement that physiological accuracy has not been verified.
