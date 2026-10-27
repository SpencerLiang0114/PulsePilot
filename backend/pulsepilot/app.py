import asyncio
import math
import os
import struct
import time
from contextlib import suppress
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from . import agents
from .coaching import MeasurementCoach
from .estimator import FacePhysEstimator, weights_available
from .reports import build_report
from .schemas import SessionCommand, SessionConfig
from .sensing import ReliabilityGate
from .simulation import simulated_sample

app = FastAPI(title="PulsePilot", version="0.1.0")
origins = [origin.strip() for origin in os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=[])
model_lock = asyncio.Lock()
model_status = {"ready": False, "error": None}
MAX_FRAME_BYTES = 1_500_000
FRAME_TIMEOUT = 15
SESSION_TIMEOUT = 240


async def run_inference(function, *args):
    # Cancelling to_thread does not stop its worker. Keep the slot until it finishes.
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        with suppress(Exception):
            await task
        raise


@app.get("/health")
async def health():
    return {"status": "ok", "weights_available": weights_available(),
            "model_ready": model_status["ready"], "model_error": model_status["error"],
            "busy": model_lock.locked(), "ai_configured": agents.configured(), "model": "FacePhys.rlap"}


def decode_frame(data: bytes):
    if not 16 < len(data) <= MAX_FRAME_BYTES:
        raise ValueError("Frame exceeds the size limit or is empty.")
    timestamp = struct.unpack("<d", data[:8])[0]
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("Invalid capture timestamp.")
    # Only accept PNG and inspect IHDR before decompression to bound decoded memory.
    png = data[8:]
    if (not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) < 33
            or png[8:16] != b"\x00\x00\x00\x0dIHDR"):
        raise ValueError("Expected a PNG frame.")
    width, height = struct.unpack(">II", png[16:24])
    if not 32 <= width <= 640 or not 32 <= height <= 480:
        raise ValueError("Frame resolution must be between 32×32 and 640×480.")
    bgr = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Could not decode frame.")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), timestamp


@app.websocket("/ws/measure")
async def measurement(ws: WebSocket):
    if ws.headers.get("origin") not in origins:
        await ws.close(code=1008, reason="Origin is not allowed.")
        return
    await ws.accept()
    estimator = None
    has_slot = False
    pending: set[asyncio.Task] = set()
    coach = None
    decision_task = None
    decision_proposal_id = None
    samples = []
    ai_status = "not_configured"
    initializing = False
    send_lock = asyncio.Lock()

    async def send(payload):
        async with send_lock:
            await ws.send_json(payload)

    try:
        config = SessionConfig.model_validate(await asyncio.wait_for(ws.receive_json(), 10))
        if config.mode != "simulation" and not config.frame_consent:
            raise ValueError("Consent to sending frames to the inference service is required.")
        if config.ai_consent and agents.configured():
            ai_status = "ready"
        elif not config.ai_consent:
            ai_status = "not_requested"
        coach = MeasurementCoach(mode="meta" if ai_status == "ready" and config.coaching == "meta"
                                 else "passive" if config.coaching == "passive" else "rules",
                                 rule_status=f"fallback_{ai_status}" if config.coaching == "meta" else "rules")
        decision_agent = agents.SensingDecisionAgent()
        if config.mode != "simulation":
            if model_lock.locked():
                await send({"type": "error", "message": "The inference service is measuring another session. Try again shortly."})
                return
            await model_lock.acquire()
            has_slot = True
            initializing = True
            model_status.update(ready=False, error=None)
            await send({"type": "status", "state": "Initializing", "message": "Warming up FacePhys. The first session may take a moment."})
            estimator = FacePhysEstimator()
            await run_inference(estimator.start)
            model_status.update(ready=True, error=None)
            initializing = False
        await send({"type": "ready", "mode": config.mode, "ai_status": ai_status})
        gate = ReliabilityGate()
        target = config.duration
        simulation_t, last_sample = 0.0, -1.0
        last_heatmap_tick = -1
        wall_started = time.monotonic()

        async def emit(sample):
            nonlocal last_sample, decision_task, decision_proposal_id
            samples.append(sample)
            last_sample = sample.t
            coach.update(sample, target-sample.t)
            if decision_task is not None:
                if coach.proposal is None or coach.proposal.proposal_id != decision_proposal_id:
                    decision_task.cancel()
                if decision_task.done():
                    if not decision_task.cancelled():
                        coach.resolve(decision_proposal_id, decision_task.result(), sample, target-sample.t)
                    decision_task = None
            if coach.proposal is not None and decision_task is None:
                decision_proposal_id = coach.proposal.proposal_id
                decision_task = asyncio.create_task(decision_agent.decide(coach.proposal))
                pending.add(decision_task)
                decision_task.add_done_callback(pending.discard)
            await send({"type": "sample", "sample": sample.model_dump(),
                        "coaching_state": coach.state, "coaching_mode": config.coaching,
                        "interventions": [i.model_dump() for i in coach.interventions]})

        while time.monotonic()-wall_started < SESSION_TIMEOUT:
            try:
                message = await asyncio.wait_for(ws.receive(), 0.125 if config.mode == "simulation" else FRAME_TIMEOUT)
            except TimeoutError:
                if config.mode != "simulation":
                    raise ValueError("No camera frames arrived for fifteen seconds. Restart measurement.")
                simulation_t += 0.5
                await emit(simulated_sample(simulation_t, gate))
                if simulation_t >= target:
                    break
                continue
            if message["type"] == "websocket.disconnect":
                return
            if message.get("text") is not None:
                try:
                    command = SessionCommand.model_validate_json(message["text"])
                except ValidationError as exc:
                    raise ValueError("Expected a session command: finish or extend.") from exc
                if command.type == "finish":
                    break
                if command.type == "extend":
                    target = min(180, target+30)
                    await send({"type": "duration", "duration": target})
                continue
            if config.mode == "simulation":
                raise ValueError("Simulation does not accept camera frames.")
            rgb, timestamp = await asyncio.to_thread(decode_frame, message.get("bytes", b""))
            if estimator.start_time is not None and timestamp-estimator.start_time > 181:
                raise ValueError("Capture timestamp exceeded the session limit.")
            await run_inference(estimator.push, rgb, timestamp)
            if coach.proposal and (not estimator.camera.face_visible or estimator.camera.face_count != 1):
                coach.proposal = None
                coach.state = "MONITORING"
                if decision_task is not None:
                    decision_task.cancel()
            elapsed = timestamp-estimator.start_time
            heatmap_tick = math.floor(elapsed*60 + 1e-6)
            if heatmap_tick > last_heatmap_tick:
                heatmap = await run_inference(estimator.heatmap)
                await send({"type": "face_heatmap", "heatmap": heatmap.model_dump() if heatmap else None,
                            "t": elapsed, "camera": estimator.camera.model_dump()})
                last_heatmap_tick = heatmap_tick
            if elapsed-last_sample >= 0.49:
                sample = await run_inference(estimator.snapshot)
                await emit(sample)
            await send({"type": "ack"})
            if elapsed >= target:
                break
        coach.finish(samples[-1].t if samples else 0)
        if estimator:
            await run_inference(estimator.close)
            estimator = None
        if has_slot:
            model_lock.release()
            has_slot = False
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        report = build_report(config, samples, coach.interventions)
        report.ai_status = "pending" if ai_status == "ready" else ai_status
        await send({"type": "report", "report": report.model_dump()})
        if ai_status == "ready":
            report = await agents.analyze_report(report)
            await send({"type": "report", "report": report.model_dump()})
    except WebSocketDisconnect:
        pass
    except (TimeoutError, ValueError, ValidationError, RuntimeError) as exc:
        if initializing or (estimator and isinstance(exc, (RuntimeError, TimeoutError))):
            model_status.update(ready=False, error="Model initialization or inference failed; inspect server diagnostics.")
        with suppress(RuntimeError, WebSocketDisconnect):
            await send({"type": "error", "message": str(exc)[:300] or "The inference service timed out. Restart measurement."})
    except Exception:
        if has_slot:
            model_status.update(ready=False, error="Inference initialization or processing failed.")
        with suppress(RuntimeError, WebSocketDisconnect):
            await send({"type": "error", "message": "The inference service could not process this session. Check the backend setup and restart."})
        # Stack traces exclude frames and request payloads.
        import logging
        logging.getLogger("pulsepilot").exception("Inference session failed")
    finally:
        if coach is not None:
            coach.finish(samples[-1].t if samples else 0)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        try:
            if estimator:
                await run_inference(estimator.close)
        finally:
            if has_slot:
                model_lock.release()
            with suppress(RuntimeError, WebSocketDisconnect):
                await ws.close()
