# Deployment runbook

Use a persistent inference process. The initial capacity limit is one real measurement per Python process. Model state remains connection-local. CPU smoke throughput is not a hosted performance guarantee.

## Local website

Follow README setup, start Python on port 8000 and Next.js on 3000. The first measurement initializes the real checkpoint and JAX compilation; later sessions reuse compiled functions with independent temporal state. `GET /health` distinguishes installed weights from a successfully initialized model.

For a local production frontend, run `pnpm build` followed by `pnpm start` from the repository root while Python remains running. The startup script defaults to `127.0.0.1:3000`; set `PORT` or `HOSTNAME` to override those values.

## Vercel frontend and persistent inference

1. Provision a persistent Linux CPU or CUDA GPU host that supports long-lived WebSockets. Build `backend/Dockerfile` from the repository root. The default image uses CPU JAX; do not claim GPU acceleration merely because the host has a GPU. A CUDA deployment needs a separately tested compatible JAX/CUDA image.
2. Serve the backend over HTTPS/WSS. Set `ALLOWED_ORIGINS` to the exact frontend HTTPS origin, not `*`. Keep one Uvicorn worker. The host must allow initialization and sessions lasting up to four minutes.
3. Authenticate Vercel, then set `NEXT_PUBLIC_BACKEND_URL` to that HTTPS backend before building/deploying. The frontend includes no secrets.
4. Optionally set server-only `MODEL_API_KEY`, `META_MODEL`, and `AGENT_MODE` on the Python service. Users must additionally opt in before numerical summaries are sent to Meta.
5. Visit the deployed site, perform a real consenting-user camera session, verify actual frame rate and no stale BPM, finish, and inspect report provenance. Confirm idle/disconnect frees the inference slot.

Update the Vercel CLI using `npm i -g vercel@latest` before deployment and authenticate with the intended hosting account. No hosted deployment is certified by a local build.

## Modal backend deployment

`backend/modal_app.py` builds the existing backend Dockerfile on Modal. It uses four CPU cores, 4 GiB RAM, one container maximum, one Uvicorn worker, and eight concurrent connections so health checks and busy responses remain available during a measurement. The existing lock still permits only one real measurement at a time. Idle containers scale to zero with a 300-second scaledown window; cold starts and JAX compilation recur after idle shutdown.

The Modal deployment token authorizes hosting. `MODEL_API_KEY` authorizes Meta model calls; it does not deploy infrastructure. Only `MODEL_API_KEY`, `META_MODEL`, `AGENT_MODE`, and `ALLOWED_ORIGINS` are injected into the backend. Modal, Baseten, and Fireworks credentials are not forwarded into the hosted service.

From the repository root, after storing credentials in ignored `backend/.env`:

```sh
uv run --no-project --python 3.12 --with modal==1.6.3 --with python-dotenv==1.2.4 python - <<'PY'
import os
import subprocess
from dotenv import load_dotenv

load_dotenv("backend/.env")
os.environ.pop("MODAL_PROFILE", None)
os.environ["ALLOWED_ORIGINS"] = "https://pulsepilot-xi.vercel.app"
# On this development machine the configured proxy stalls Modal's API connection.
os.environ["MODAL_DISABLE_API_PROXY"] = "1"
subprocess.run(["modal", "deploy", "backend/modal_app.py"], check=True)
PY
```

Keep the exact origin synchronized with the frontend domain. A new preview hostname must be explicitly allowed before camera/WebSocket testing. Set Vercel's production `NEXT_PUBLIC_BACKEND_URL` to the Modal HTTPS origin before deploying the frontend. `.vercelignore` excludes the Python backend and environment files from frontend uploads.

### Hosted demo — November 1, 2026

- Frontend: <https://pulsepilot-xi.vercel.app>, Vercel project `pulsepilot` in `spencerliang0114s-projects`, Node.js 24.
- Backend: <https://spencerliang0114--pulsepilot-inference.us-east.modal.run>, Modal app `pulsepilot`.
- Frontend source: `a64d9b5`; deployment configuration is recorded in this change. No Git push or automatic Git deployment was configured.
- Verified: production build and TypeScript, browser page rendering without JavaScript errors, browser cross-origin `/health`, simulated WebSocket sample/report delivery, real checkpoint initialization, camera-protocol report delivery, and model-slot release. Initial hosted FacePhys initialization took 46.89 seconds. No camera frames were used in that initialization check.
- A separate 30-second Chromium synthetic-camera run reached the report screen through the public production URL. It delivered 58 observation windows, no face or accepted heart-rate values, and about 12.1 processed fps from a 20-fps fake camera. Mean acknowledgement round trip was 278 ms. This verifies transport/report delivery, not adequate live-camera throughput or physiological accuracy. An earlier synthetic-camera run did not reach the report before the test timeout; no cause was established.
- A hosted 30-second simulation with synthetic evidence completed Muse report interpretation and Health Insights. Accepted model responses took approximately 2.59 and 2.10 seconds respectively. One coaching explanation hit its 1.5-second timeout and fell back to deterministic guidance. This is one synthetic check, not a provider reliability guarantee.
- Production is public; Vercel Authentication remains enabled for preview deployments (`ssoProtection.deploymentType=preview`). The production URL returned HTTP 200 without authentication.
- Physical-camera throughput, reference-device accuracy, and multi-user performance require separate hosted validation.

## Single-origin container demo

```sh
docker compose up --build
```

Open http://localhost:8080. The included Caddy configuration proxies all routes through one origin and avoids cross-origin camera transport. It exposes only loopback. For remote access, put an HTTPS reverse proxy or temporary HTTPS tunnel in front of port 8080.

When using a public URL, set `PUBLIC_ORIGIN=https://your-host` before building the frontend and starting the containers; this sets the exact origin allowlist and client URL. The initial tunnel hostname may need to be obtained before building. Do not expose port 8000 directly to the internet.

`docker compose` does not automatically read `backend/.env`. Export `MODEL_API_KEY` in the shell or supply it through your secret manager; `.env` files and keys are excluded from container build contexts.

P2 defaults to `AGENT_MODE=assist`. Compose passes `${AGENT_MODE:-assist}` to the inference service; export `AGENT_MODE=off`, `observe`, or `adaptive` before starting Compose to change behavior. On a directly hosted backend set the same server environment variable before Uvicorn. Adaptive selection is opt-in; every remote model transfer still requires per-session AI consent. LangGraph is installed from the frozen backend lockfile by the existing Dockerfile. See [P2 deployment and privacy details](langgraph-p2.md).

## Temporary demo without containers

Build Next.js with `INFERENCE_INTERNAL_URL=http://127.0.0.1:8000 pnpm build`, then start it with `PORT=3001 pnpm start`. Next.js proxies the fixed `/health` and `/ws/measure` routes to Python. Leave `NEXT_PUBLIC_BACKEND_URL` unset so a public browser uses its own HTTPS origin.

Run `cloudflared tunnel --url http://127.0.0.1:3001` against that production server, then add the generated exact HTTPS origin to Python's `ALLOWED_ORIGINS` and restart Python. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) require no account, but the random URL expires when the tunnel stops and has no uptime guarantee. This is a temporary demonstration, not permanent hosting. Keep the Mac awake and all three processes running.

## Scope and checkpoints

- Verify checkpoint licensing with its author before redistribution/commercial deployment; upstream distinguishes model rights from its source MIT license.
- Prefer a persistent process over serverless JAX cold starts.
- Benchmark full PNG capture/decode/inference at ≥24 actual fps, with a 30-fps target.
- A healthy server, model-only smoke test, synthetic camera test, and simulated report are separate from real human measurement and reference accuracy.
- No database and no disk recording: session data are in process memory until delivery and in page memory until reload/export.
