# Verification record

October 20, 2026. These are executed checks, not a claim that every MVP acceptance gate has been met.

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

## Not verified / external dependencies

- **Muse Spark live access:** the user will receive a hackathon key later. The official API integration, strict response schemas, and failure paths are implemented/tested with mocked HTTP responses. No live Meta request or AI-generated report is claimed.
- **Consenting-user heart rate:** no suitable human video or live physical-camera measurement was provided. A user still needs to complete this acceptance check.
- **Physiological accuracy:** no synchronized reference data, clinical testing, or accuracy across skin tones/cameras/lighting. Higher SQI and lower variance do not establish accuracy.
- **Permanent hosting:** the public URL is an active temporary tunnel to this Mac. It expires when the process stops and is unavailable if the Mac sleeps. Vercel authentication and persistent hosting are not provisioned.
- **Container execution:** Docker CLI/Compose are present, but the Docker daemon is not running; images were not built/run.
- **SAM:** evaluated from official API documentation and intentionally excluded. No additional value has yet been measured.
- **Checkpoint rights:** upstream explicitly distinguishes model licensing from MIT source licensing; FacePhys-specific redistribution/commercial terms were not established.

## Known runtime notes

macOS logs duplicate AVFoundation classes when PyAV and OpenCV load their bundled FFmpeg libraries. No crash occurred in the executed checks; Linux container behavior remains untested. The upstream normalizer warns on flat/no-face signals; PulsePilot suppresses invalid BPM. Starlette's TestClient emits an httpx deprecation warning, without test failures.

## Definition-of-done status

Website, capture/transport, real pretrained inference execution, deterministic sensing/guidance, closed-loop comparisons, session reports, simulation/replay, and a temporary HTTPS demonstration are integrated. Final completion still requires a real consenting-user measurement, authenticated Muse Spark calls, and the chosen durable deployment. Reference-device validation remains a separate scientific evaluation.
