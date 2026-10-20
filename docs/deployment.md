# Deployment runbook

Use a persistent inference process. The initial capacity limit is one real measurement per Python process. Model state remains connection-local. CPU smoke throughput is not a hosted performance guarantee.

## Local website

Follow README setup, start Python on port 8000 and Next.js on 3000. The first measurement initializes the real checkpoint and JAX compilation; later sessions reuse compiled functions with independent temporal state. `GET /health` distinguishes installed weights from a successfully initialized model.

## Vercel frontend and persistent inference

1. Provision a persistent Linux CPU or CUDA GPU host that supports long-lived WebSockets. Build `backend/Dockerfile` from the repository root. The default image uses CPU JAX; do not claim GPU acceleration merely because the host has a GPU. A CUDA deployment needs a separately tested compatible JAX/CUDA image.
2. Serve the backend over HTTPS/WSS. Set `ALLOWED_ORIGINS` to the exact frontend HTTPS origin, not `*`. Keep one Uvicorn worker. The host must allow initialization and sessions lasting up to four minutes.
3. Authenticate Vercel, then set `NEXT_PUBLIC_BACKEND_URL` to that HTTPS backend before building/deploying. The frontend includes no secrets.
4. Add `MODEL_API_KEY` to the Python service when hackathon access is provided. Users must additionally opt in before numerical summaries are sent to Meta.
5. Visit the deployed site, perform a real consenting-user camera session, verify actual frame rate and no stale BPM, finish, and inspect report provenance. Confirm idle/disconnect frees the inference slot.

The Vercel CLI installed in the development environment reported 53.2.0 and no saved credentials. Update using `npm i -g vercel@latest` before deployment. No hosted deployment is certified by a local build.

## Single-origin container demo

```sh
docker compose up --build
```

Open http://localhost:8080. The included Caddy configuration proxies all routes through one origin and avoids cross-origin camera transport. It exposes only loopback. For remote access, put an HTTPS reverse proxy or temporary HTTPS tunnel in front of port 8080.

When using a public URL, set `PUBLIC_ORIGIN=https://your-host` before building the frontend and starting the containers; this sets the exact origin allowlist and client URL. The initial tunnel hostname may need to be obtained before building. Do not expose port 8000 directly to the internet.

`docker compose` does not automatically read `backend/.env`. Export `MODEL_API_KEY` in the shell or supply it through your secret manager; `.env` files and keys are excluded from container build contexts.

## Temporary demo without containers

Build Next.js with `INFERENCE_INTERNAL_URL=http://127.0.0.1:8000 pnpm build`, then start it on a local port. Next.js proxies the fixed `/health` and `/ws/measure` routes to Python. Leave `NEXT_PUBLIC_BACKEND_URL` unset so a public browser uses its own HTTPS origin.

Run `cloudflared tunnel --url http://127.0.0.1:3001` against that production server, then add the generated exact HTTPS origin to Python's `ALLOWED_ORIGINS` and restart Python. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) require no account, but the random URL expires when the tunnel stops and has no uptime guarantee. This is a temporary demonstration, not permanent hosting. Keep the Mac awake and all three processes running.

## Scope and checkpoints

- Verify checkpoint licensing with its author before redistribution/commercial deployment; upstream distinguishes model rights from its source MIT license.
- Prefer a persistent process over serverless JAX cold starts.
- Benchmark full PNG capture/decode/inference at ≥24 actual fps, with a 30-fps target.
- A healthy server, model-only smoke test, synthetic camera test, and simulated report are separate from real human measurement and reference accuracy.
- No database and no disk recording: session data are in process memory until delivery and in page memory until reload/export.
