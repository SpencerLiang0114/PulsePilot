# FacePhys inference service

The persistent FastAPI service in `backend/pulsepilot/app.py` implements the protocol used by the website. Each camera or recording session owns a fresh frozen `FacePhys.rlap` model and its temporal state. One real inference session is allowed per process; simulation does not occupy that slot.

## Run locally

From the repository root:

```sh
uv run scripts/fetch_facephys.py
cd backend
uv sync --frozen
# On first setup only; preserve an existing .env.
cp -n .env.example .env
uv run uvicorn pulsepilot.app:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 1500000
```

Run `pnpm dev` in another terminal at the repository root. The frontend defaults to `http://localhost:8000`; `NEXT_PUBLIC_BACKEND_URL` overrides it. `ALLOWED_ORIGINS` in `backend/.env` is a comma-separated list of exact frontend origins. HTTPS deployments require an HTTPS/WSS backend or the documented same-origin reverse proxy.

No API key is required for FacePhys. Optional Muse interpretation uses server-only credentials and separate `ai_consent`. Model setup and checkpoint provenance are documented in [FacePhys integration](facephys-integration.md).

## Health

`GET /health` returns process health, checkpoint presence, `busy`, `model_ready`, `model_error`, and `ai_configured`.

`model_ready` means the most recent model initialization succeeded without a subsequently observed model failure. It starts false and resets during startup or on failure; it can remain true between sessions. It does not mean a model is currently assigned, a face is visible, or a BPM is available. `busy` remains true until model work and cleanup finish, including after request cancellation. A missing checkpoint does not disable simulation or the health endpoint.

## WebSocket protocol

Connect to `/ws/measure` with an allowed `Origin` header. Within ten seconds, send a JSON configuration:

```json
{"type":"start","mode":"camera","duration":60,"frame_consent":true,"ai_consent":false,"coaching":"rules"}
```

Modes are `camera`, `recording`, or `simulation`. Duration is 30–180 seconds. Camera and recording require frame consent. Coaching accepts `passive`, `rules`, or `meta`.

The server sends `status` during FacePhys warmup, then `ready`. Wait for `ready` before sending frames. A second real session receives an actionable `error` and closes; the active session keeps its model state.

Each binary message contains:

| Offset | Value |
|---|---|
| 0–7 | Little-endian float64 capture timestamp in seconds |
| 8 onward | Lossless PNG frame |

Timestamps must be finite, nonnegative, and strictly increasing. Use the camera or recording presentation clock, not send time. Image dimensions must be 32–640 pixels wide and 32–480 high, and the entire message must be at most 1,500,000 bytes. The server validates the PNG header and dimensions before image decoding, converts the image to RGB, and uses the original FacePhys detector/crop pipeline. The browser currently fits frames into 320×240 and limits transport to four frames in flight.

The server acknowledges each processed frame with `{"type":"ack"}` and emits `sample` messages about twice per second:

```json
{"type":"sample","sample":{"t":0.0,"bpm":null,"sqi":null,"usable":false,"state":"Measuring","fps":0.0,"latency_ms":0.0,"camera":{},"waveform":[]},"interventions":[],"coaching_state":"MONITORING","coaching_mode":"meta"}
```

This abbreviated example omits the camera metrics; the full schemas are in `backend/pulsepilot/schemas.py`. `t` is relative to the first capture timestamp. `waveform` contains finite BVP samples, `sqi` measures periodicity, and `bpm` stays null until the reliability gate accepts sufficient fresh signal. Gaps over 250 ms reset the model and measurement window. Capture cadence, single-face visibility, lighting, motion, signal periodicity, and processing lag all affect acceptance. These checks do not establish physiological accuracy.

`coaching_state` is `MONITORING`, `DECIDING`, `ACTING`, `OBSERVING`, or `COOLDOWN`. A pending decision has no new committed intervention. Each intervention includes `action_id`, `decision_source`, `explanation_source`, `decision_status`, pre/post SQI and usable fractions, averaged camera metrics and environmental changes. Reports also export the deterministic typed claim catalogue. See [agent design](agent-design.md) for selection, revalidation, fallback and cancellation behavior.

Supported JSON commands after readiness:

- `{"type":"extend"}` adds 30 seconds, capped at 180; the server replies with `duration`.
- `{"type":"finish"}` stops inference, releases capacity, sends a `report`, and closes. The report keeps numerical samples but omits waveform arrays. With configured and consented AI, the numerical report arrives first with `ai_status: "pending"`, followed by the completed interpretation.

Malformed commands or frames produce an `error` and close the session. Fifteen seconds without a message ends a real session with an error; the measurement loop has a 240-second wall-clock bound. Capture duration also ends the session automatically. Disconnects and failures release capacity. Cancellation waits for in-flight model work before closing workers; it cannot forcibly terminate a stuck native call. Initialization and inference run off the event loop so health requests remain responsive.

## Verification

```sh
cd backend
uv run pytest -q
uv run ruff check pulsepilot tests ../scripts
uv run python ../scripts/smoke_facephys.py
RUN_FACEPHYS_INTEGRATION=1 uv run pytest -q tests/test_facephys_integration.py
```

The default suite uses controlled estimator fixtures for lifecycle tests. The opt-in test loads the actual checkpoint, sends 330 synthetic PNG frames at nominal 30 Hz through the WebSocket handler, finishes a report, and starts a fresh recording session. It requires fetched weights and takes longer because of JAX compilation. The standalone smoke script also exercises the frozen model directly and checks finite BVP output.

With frontend and backend running, `pnpm test:e2e tests/experience.spec.ts --grep 'recording runs|real FacePhys'` exercises browser capture/recording transport and cleanup. All generated-frame checks must suppress BPM for blank images. They verify execution and transport, not a human heart-rate measurement. See [verification](verification.md) for recorded results.
