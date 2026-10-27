# PulsePilot architecture

Updated for P2 on October 27, 2026. This is a research demonstration, not a medical device. [The P2 guide](langgraph-p2.md) defines the current graphs, operating modes, lifecycle, and verification scope.

## Vertical slice

```text
Browser camera or user-selected recording
  → timestamp + lossless PNG over WebSocket
  → FastAPI session (one isolated FacePhys state per connection)
  → FacePhys.rlap → BVP, HR, periodicity SQI
  → camera metrics + conservative validity gate
  → persistent candidates → mode-controlled LangGraph proposal/explanation → coach-validated instruction
  → observe → deterministic comparison → session-local outcome memory → next decision
  → live website + deterministic session statistics
  → LangGraph report workflow → Muse Spark typed claim references → server-rendered report
```

Next.js/React/TypeScript owns the camera, preview, charts, controls, report history, and export. Python/FastAPI owns inference, timing validation, quality metrics, intervention outcomes, and reports. Browser capture is the only webcam owner; Python never opens a camera. No database is needed: keep reports in browser memory until the page closes, with explicit JSON and print export.

Use a single long-running inference process initially, with one active real session and bounded duration. JAX compilation happens before accepting frames. CPU operation is measured first; a persistent Linux GPU host is the upgrade path if real-time throughput is inadequate. Never put this JAX pipeline into a Next.js route handler.

## Transport and lifecycle

`GET /health` reports actual model readiness and whether Meta credentials are configured. `WS /ws/measure` accepts a configuration message, initializes the model, then sends readiness. A binary frame consists of an eight-byte little-endian capture timestamp in seconds plus PNG image bytes. At most four frames are in flight in the browser, with a byte-buffer cap; frame ACKs provide backpressure while allowing network round trips longer than one camera frame. Timestamp discontinuity resets the temporal window; low capture rate suppresses BPM. A finish command returns numerical results immediately, followed by AI analysis when available. Disconnect, cancellation, idle timeout, maximum duration, and initialization failure all release the model slot.

Camera metrics are sampled alongside inference; live summaries are emitted at 2 Hz. Browser transport scales the source proportionally to fit 320×240 before lossless PNG encoding; FacePhys retains its own original face detection/cropping and 36×36 model preprocessing. Frames are decoded in a worker thread. Slow Meta requests run as independent tasks and never hold the frame-processing loop. Origin allowlisting, message-size limits, a finite session duration, and a single-session capacity limit bound the public demo.

The orchestration service owns event identities and bounded execution per WebSocket. It runs only quality/coaching/report events, never per-frame inference. `off` skips graphs; `observe` collects diagnostics; default `assist` enriches rules-selected actions; explicit `adaptive` permits eligible action selection before commitment. Separate AI consent gates every remote request. Coaching has a 1.5-second application deadline; the coach revalidates every asynchronous result. Numerical reports arrive after inference resources are released, ahead of optional analysis. Disconnect cancels pending analysis. Local telemetry excludes measurement payloads and external tracing is disabled.

## Privacy

The start dialog explicitly explains that frames leave the browser for the configured inference service and are discarded after processing. Audio is never captured. Muse Spark receives only structured numerical summaries and intervention records, with separate opt-in for that transfer. No images go to Meta. Raw video, API keys, and physiological payloads must not be logged. Report exports are the user's explicit action.

## Deployment options

| Option | Use | Limits |
|---|---|---|
| Vercel frontend + persistent HTTPS/WSS inference host | Public demo | Requires an authenticated Vercel account and an inference host; test network throughput and JAX runtime |
| Same-origin reverse proxy + Next.js + Python containers | Predictable hosted demo | Persistent VM; TLS and process supervision required |
| Local Next.js + local inference, both through one HTTPS tunnel | Short hackathon demonstration | Laptop must remain awake; tunnel URL is temporary; capacity is one measurement |
| HTTPS frontend + plain localhost backend | Local development only | Mixed-content/private-network restrictions vary; do not promise public compatibility |

The [P2 verification record](verification.md#p2-langgraph-verification) distinguishes fixture, checkpoint, browser, and live-provider checks. In the recorded live P2 run, coaching requests used deadline fallback and the final Muse report validated. Timely live adaptive selection, persistent hosting, and human-camera validation remain unverified. The application retains deterministic measurements and reports when optional services are unavailable.

## Repository

`app/`, `components/`, `lib/`: website. `backend/pulsepilot/`: estimator, sensing, coaching, schemas, report analyst, server. `backend/tests/`: numerical, lifecycle, and agent tests. `scripts/`: pinned upstream fetch, real inference smoke test, replay evaluation. `docs/`: design and verification evidence.
