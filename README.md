# PulsePilot

A webcam heart-rate research application combining pretrained FacePhys sensing, camera coaching, measured intervention outcomes, and evidence-grounded session reports.

The browser captures video; a persistent Python service runs frozen `FacePhys.rlap`; Muse Spark interprets structured metrics when configured. The website supports real camera input, recorded-video replay, and clearly labeled synthetic quality scenarios.

Temporary demo, verified October 20, 2026: **[Open PulsePilot](https://painting-everybody-richardson-cape.trycloudflare.com)**. This URL depends on the development Mac and tunnel staying running; it is not permanent hosting. The current local production preview is at http://127.0.0.1:3001.

## Development

Requires Node.js 22+, pnpm, uv, and Python 3.12.

```sh
pnpm install
uv run scripts/fetch_facephys.py
cd backend
uv sync
cp .env.example .env
uv run uvicorn pulsepilot.app:app --host 127.0.0.1 --port 8000
```

In another terminal, run `pnpm dev` at the repository root and open http://localhost:3000. Set `MODEL_API_KEY` in `backend/.env` to enable Muse Spark. No key is needed for FacePhys, deterministic guidance, or numerical reports. Users opt in separately before sending structured metrics to Meta. Never add an API key to a `NEXT_PUBLIC_` variable.

The upstream source/checkpoint is downloaded to ignored `.vendor/open-rppg` at a pinned commit. Its source is MIT, but the upstream license distinguishes pretrained-model rights; see [integration notes](docs/facephys-integration.md).

## Checks

```sh
pnpm check
pnpm build
cd backend
uv run pytest
uv run python ../scripts/smoke_facephys.py
```

With both services running, `pnpm test:e2e` runs the browser tests. Set `PULSEPILOT_TEST_URL` to run them against an HTTPS deployment. The camera and recording tests generate synthetic frames, never access a physical camera, and assert that blank frames cannot produce a usable BPM.

Replay a consenting user's recording through the real estimator:

```sh
cd backend
uv run python ../scripts/replay.py /path/to/video.mp4 --output /path/to/report.json
```

Add `--coaching passive` for the passive baseline or `--reference /path/to/reference.csv` for a synchronized `t,bpm` comparison. No reference accuracy is reported without supplied reference data.

See [verification](docs/verification.md) for actual results and remaining external gates.

## Deployment

Deploy the Next.js frontend to Vercel with `NEXT_PUBLIC_BACKEND_URL=https://your-inference-host`. Run the Python Dockerfile on a persistent CPU/GPU host with WebSocket support. Set `ALLOWED_ORIGINS` to the exact HTTPS frontend origin, `FACEPHYS_ROOT` to the downloaded upstream tree, and server-only `MODEL_API_KEY`. Start with one inference session per process and benchmark before increasing capacity.

A second option is `docker compose up --build` behind a TLS reverse proxy forwarding `/ws/` and `/health` to Python and the remaining paths to Next.js. For a short demo, tunnel this same-origin proxy over HTTPS; do not point a public HTTPS website at plain HTTP localhost.

A persistent hosted deployment requires hosting authentication and a reachable inference service. Do not treat a frontend-only URL as a completed demonstration. The installed Vercel CLI reported 53.2.0; upgrade before deployment with `npm i -g vercel@latest`.

The current temporary URL uses a same-origin Next.js proxy and Cloudflare tunnel to the local inference process. See the [deployment runbook](docs/deployment.md) for hosted and container alternatives.

## Design

- [Architecture](docs/architecture.md)
- [FacePhys source/API audit](docs/facephys-integration.md)
- [Backend service and WebSocket protocol](docs/backend-service.md)
- [Website experience](docs/web-experience.md)
- [Agent design and verified Meta APIs](docs/agent-design.md)
- [Phases and acceptance criteria](docs/implementation-plan.md)
- [Evaluation protocol](docs/evaluation.md)

PulsePilot does not diagnose conditions. A stable rPPG waveform does not guarantee an accurate heart rate. Frames are processed transiently; reports remain in page memory until explicitly exported or the page closes.
