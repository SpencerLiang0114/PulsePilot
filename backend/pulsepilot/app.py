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
from .orchestration.service import OrchestrationService, as_decision, configured_mode
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
            "busy": model_lock.locked(), "ai_configured": agents.configured(), "model": "FacePhys.rlap",
            "agent_mode": configured_mode()}


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
    decision_event = None
    orchestration = None
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
        orchestration = OrchestrationService(ai_consent=config.ai_consent)
        if orchestration.mode == "off":
            ai_status = "disabled"
        elif config.ai_consent and agents.configured():
            ai_status = "ready"
        elif not config.ai_consent:
            ai_status = "not_requested"
        coach = MeasurementCoach(mode="meta" if (ai_status == "ready" and config.coaching == "meta"
                                                 and orchestration.mode == "adaptive")
                                 else "passive" if config.coaching == "passive" else "rules",
                                 rule_status=(f"fallback_{ai_status}" if config.coaching == "meta"
                                              and ai_status not in ("ready", "disabled") else "rules"))
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
        playback_rate = 1 if config.mode != "simulation" or coach.mode == "meta" else 4
        await send({"type": "ready", "mode": config.mode, "ai_status": ai_status,
                    "playback_rate": playback_rate,
                    "agent_mode": orchestration.mode, "session_id": orchestration.session_id})
        gate = ReliabilityGate()
        target = config.duration
        simulation_t, last_sample = 0.0, -1.0
        last_heatmap_tick = -1
        wall_started = time.monotonic()

        async def emit(sample):
            nonlocal last_sample, decision_task, decision_proposal_id, decision_event
            samples.append(sample)
            last_sample = sample.t
            committed = coach.update(sample, target-sample.t)
            if decision_task is not None:
                if decision_event.purpose == "select" and (
                    coach.proposal is None or coach.proposal.proposal_id != decision_proposal_id
                ):
                    decision_task.cancel()
                if decision_task.done():
                    if not decision_task.cancelled():
                        outcome = decision_task.result()
                        item = None
                        if decision_event.purpose == "select" and outcome.route != "discarded":
                            item = coach.resolve(decision_proposal_id, as_decision(outcome), sample, target-sample.t)
                        elif (decision_event.purpose == "explain" and coach.active is not None
                              and coach.active.id == decision_event.context.intervention_id
                              and sample.t-coach.active.started_at <= coach.RESPONSE):
                            item = coach.active
                            if (outcome.route == "accepted" and outcome.action is not None
                                    and outcome.action.action_id == item.action_id):
                                item.explanation = outcome.action.explanation
                                item.explanation_source = "muse"
                            else:
                                item.decision_status = f"explanation_fallback_{outcome.status}"
                        if item is not None:
                            item.agent_event_id = outcome.event_id
                            item.graph_version = outcome.graph_version
                            item.model_latency_ms = outcome.model_latency_ms
                            item.graph_latency_ms = outcome.graph_latency_ms
                    decision_task = None
            event = None
            if coach.proposal is not None and decision_task is None:
                decision_proposal_id = coach.proposal.proposal_id
                event = orchestration.coach_event(coach.proposal, "select")
            elif (committed is not None and orchestration.mode in ("assist", "observe") and config.coaching == "meta"
                  and decision_task is None
                  and (orchestration.mode == "observe" or committed.issue not in ("face", "cadence"))):
                candidates = coach.candidates(sample)
                if orchestration.mode == "assist":
                    candidates = [c for c in candidates if c.action_id == committed.action_id]
                context = coach.decision_context(sample, target-sample.t, candidates)
                event = orchestration.coach_event(
                    context, "explain" if orchestration.mode == "assist" else "observe", committed.id,
                )
            if event is not None:
                decision_event = event
                decision_task = asyncio.create_task(orchestration.run_coach_event(event))
                pending.add(decision_task)
                decision_task.add_done_callback(pending.discard)
            await send({"type": "sample", "sample": sample.model_dump(),
                        "coaching_state": coach.state, "coaching_mode": config.coaching,
                        "interventions": [i.model_dump() for i in coach.interventions]})

        while time.monotonic()-wall_started < SESSION_TIMEOUT:
            try:
                message = await asyncio.wait_for(ws.receive(), .5/playback_rate if config.mode == "simulation" else FRAME_TIMEOUT)
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
        await orchestration.finish_measurement()
        for task in list(pending):
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        report = build_report(config, samples, coach.interventions)
        report.agent_mode = orchestration.mode
        report.agent_telemetry = orchestration.telemetry.snapshot()
        report_visible = orchestration.mode in ("assist", "adaptive") and ai_status == "ready"
        report.ai_status = "pending" if report_visible else "observed" if ai_status == "ready" else ai_status
        await send({"type": "report", "report": report.model_dump()})
        if ai_status == "ready":
            event = orchestration.report_event(report)
            analysis_task = asyncio.create_task(orchestration.run_report_event(event))
            disconnect_task = asyncio.create_task(ws.receive())
            pending.update((analysis_task, disconnect_task))
            done, _ = await asyncio.wait((analysis_task, disconnect_task), return_when=asyncio.FIRST_COMPLETED)
            if disconnect_task in done:
                return
            disconnect_task.cancel()
            await asyncio.gather(disconnect_task, return_exceptions=True)
            outcome = analysis_task.result()
            if report_visible:
                if outcome.route == "accepted":
                    report = report.model_copy(update={"analysis": outcome.analysis, "analyst": "muse",
                                                        "ai_status": "complete"})
                else:
                    report.ai_status = "unavailable"
                report.agent_event_id, report.graph_version = outcome.event_id, outcome.graph_version
                report.agent_telemetry = orchestration.telemetry.snapshot()
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
        if orchestration is not None:
            await orchestration.close()
        for task in list(pending):
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
