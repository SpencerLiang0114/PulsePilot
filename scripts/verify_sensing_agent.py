"""Opt-in real Meta loop over explicitly synthetic lighting/motion metrics.

Run from backend: .venv/bin/python ../scripts/verify_sensing_agent.py --live
No images, waveform, or human measurements are sent. This does not validate rPPG accuracy.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pulsepilot import agents
from pulsepilot.app import app
from pulsepilot.orchestration.provider import MetaProvider
from pulsepilot.orchestration.service import COACH_DEADLINE
from pulsepilot.orchestration.telemetry import Telemetry
from pulsepilot.schemas import CameraMetrics, Sample


def scenario(t, gate):
    return Sample(t=t, sqi=.3, fps=30, camera=CameraMetrics(
        face_visible=True, face_count=1, confidence=.98, face_size=.5,
        visibility_proxy=.98, brightness=25, motion=.5,
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Send synthetic metrics to Meta using the backend key")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required to authorize real API calls with synthetic metrics")
    if not agents.configured():
        parser.error("Configure MODEL_API_KEY in backend/.env first")
    timings, contexts = [], []
    original = MetaProvider.propose
    original_record = Telemetry.record

    async def measured(self, event):
        contexts.append(event.context.model_dump())
        return await original(self, event)

    def recorded(self, outcome):
        timings.append(outcome.model_dump(exclude={"action", "analysis"}))
        original_record(self, outcome)

    states = set()
    started = time.monotonic()
    with patch.dict(os.environ, {"AGENT_MODE": "adaptive"}), patch(
        "pulsepilot.app.simulated_sample", scenario
    ), patch.object(MetaProvider, "propose", measured), patch.object(
        Telemetry, "record", recorded
    ), TestClient(app) as client, client.websocket_connect(
        "/ws/measure", headers={"origin": "http://localhost:3000"}
    ) as ws:
        ws.send_json({"mode": "simulation", "duration": 90, "coaching": "meta", "ai_consent": True})
        requested_finish = False
        while True:
            message = ws.receive_json()
            if message["type"] == "sample":
                states.add(message["coaching_state"])
                completed = [i for i in message["interventions"] if i["outcome"] != "observing"]
                if len(completed) >= 2 and not requested_finish:
                    ws.send_json({"type": "finish"})
                    requested_finish = True
            if message["type"] == "error":
                raise RuntimeError(message["message"])
            if message["type"] == "report" and message["report"]["ai_status"] != "pending":
                report = message["report"]
                break
    result = {
        "scenario": "synthetic persistent darkness and motion; constant SQI; real Meta requests",
        "model": os.getenv("META_MODEL", "muse-spark-1.3"), "decision_deadline_seconds": COACH_DEADLINE,
        "elapsed_seconds": round(time.monotonic()-started, 2),
        "requests": timings, "states": sorted(states),
        "sample_count": len(report["samples"]),
        "interventions": [{k: i[k] for k in (
            "action_id", "started_at", "evaluated_at", "decision_source", "decision_status",
            "before_sqi", "after_sqi", "before_usable", "after_usable", "outcome",
        )} for i in report["interventions"]],
        "subsequent_decision_received_outcomes": any(context["outcomes"] for context in contexts),
        "report_ai_status": report["ai_status"], "report_analyst": report["analyst"],
        "physical_camera_validated": False, "reference_accuracy_validated": False,
    }
    encoded = json.dumps(result, indent=2)+"\n"
    if args.output:
        args.output.write_text(encoded)
    print(encoded, end="")
    assert len(result["interventions"]) >= 2, "The closed loop did not complete two interventions"
    assert result["subsequent_decision_received_outcomes"], "Outcome feedback was not delivered"
    assert result["report_ai_status"] == "complete", "Live Muse report did not validate; inspect recorded statuses"


if __name__ == "__main__":
    main()
