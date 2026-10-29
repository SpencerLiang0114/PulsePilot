"""Opt-in repeated live Meta decisions with synthetic metrics, never camera data.

Run from backend: .venv/bin/python ../scripts/verify_sensing_agent.py --live --trials 20
Sampling runs at wall-clock cadence while requests are pending. Completed outcome and
cooldown windows are advanced synthetically between requests; this is a policy/integration
check, not a physical-camera, throughput, human-benefit, or HR-accuracy evaluation.
"""
import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pulsepilot import agents
from pulsepilot.coaching import MeasurementCoach
from pulsepilot.orchestration.service import OrchestrationService, as_decision
from pulsepilot.schemas import CameraMetrics, Sample
from pulsepilot.timing import ADAPTIVE_DEADLINE


def scenario(t):
    return Sample(t=t, sqi=.3, fps=30, camera=CameraMetrics(
        face_visible=True, face_count=1, confidence=.98, face_size=.5,
        visibility_proxy=.98, brightness=25, motion=.5,
    ))


async def opportunity(service, coach):
    context = coach.proposal
    event = service.coach_event(context, "select")
    started = time.monotonic()
    task = asyncio.create_task(service.run_coach_event(event))
    committed = None
    ticks = 0
    try:
        while not task.done():
            await asyncio.sleep(.5)
            ticks += 1
            sample = scenario(context.sample_at+time.monotonic()-started)
            committed = coach.update(sample, 180-sample.t) or committed
        outcome = await task
        if committed is None:
            committed = coach.resolve(context.proposal_id, as_decision(outcome), sample, 180-sample.t)
        elapsed = (time.monotonic()-started)*1000
        selected = outcome.route == "accepted" and outcome.action.action_id is not None
        abstained = outcome.route == "accepted" and outcome.action.action_id is None
        category = ("accepted_selection" if selected else "valid_abstention" if abstained else
                    "timeout" if outcome.status == "timeout" else
                    "invalid_response" if outcome.status not in ("unavailable", "not_requested") else "unavailable")
        return {
            "session_id": event.session_id, "event_id": event.event_id,
            "category": category, "route": outcome.route, "status": outcome.status,
            "validation": outcome.validation.model_dump(),
            "eligible_actions": [c.action_id for c in context.candidates],
            "previous_outcomes": [r.model_dump() for r in context.outcomes],
            "selected_action": outcome.action.action_id if selected else None,
            "provider_response_received": outcome.usage.responses > 0,
            "usage": outcome.usage.model_dump(),
            "graph_latency_ms": outcome.graph_latency_ms,
            "provider_elapsed_ms": outcome.model_latency_ms,
            "provider_latency_complete": outcome.status != "timeout" and outcome.usage.responses > 0,
            "end_to_end_latency_ms": elapsed,
            "within_budget": elapsed <= ADAPTIVE_DEADLINE*1000,
            "samples_while_pending": ticks,
            "committed_intervention": committed.model_dump() if committed else None,
            "abstention_applied": abstained and coach.state == "COOLDOWN" and committed is None,
        }
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def summarize(records, trials):
    counts = Counter(r["category"] for r in records)
    validated = sum(r["category"] in ("accepted_selection", "valid_abstention") and r["within_budget"]
                    for r in records)
    commitments = [r for r in records if r["committed_intervention"]
                   and r["committed_intervention"]["decision_source"] == "muse"]
    history_accepted = any(r["previous_outcomes"] and r["category"] in (
        "accepted_selection", "valid_abstention") for r in records)
    latencies = sorted(r["end_to_end_latency_ms"] for r in records)
    rate = validated/len(records) if records else 0
    return {
        "opportunities": len(records), "requested_opportunities": trials,
        "categories": {k: counts[k] for k in ("accepted_selection", "valid_abstention", "invalid_response",
                                               "timeout", "unavailable")},
        "provider_responses": sum(r["provider_response_received"] for r in records),
        "muse_commitments": len(commitments),
        "rules_commitments": sum(bool(r["committed_intervention"]) and
                                 r["committed_intervention"]["decision_source"] == "rules" for r in records),
        "applied_abstentions": sum(r["abstention_applied"] for r in records),
        "validated_within_budget": validated, "validated_fraction": rate,
        "timeout_fraction": counts["timeout"]/len(records) if records else 0,
        "end_to_end_mean_ms": mean(latencies) if latencies else None,
        "end_to_end_max_ms": max(latencies) if latencies else None,
        "later_accepted_decision_received_outcomes": history_accepted,
        "p3_target_met": len(records) >= max(20, trials) and rate >= .9 and len(commitments) >= 2 and history_accepted,
    }


async def run_batch(trials):
    records = []
    # Each pair shares a real service/client, coach and measured outcome memory.
    for _ in range((trials+1)//2):
        coach = MeasurementCoach(mode="meta")
        service = OrchestrationService(mode="adaptive", ai_consent=True)
        try:
            for i in range(11):
                coach.update(scenario(i*.5))
            for _ in range(min(2, trials-len(records))):
                record = await opportunity(service, coach)
                records.append(record)
                print(f"Opportunity {len(records)}/{trials}: {record['category']}; "
                      f"commit={record['committed_intervention']['decision_source'] if record['committed_intervention'] else 'none'}; "
                      f"{record['end_to_end_latency_ms']:.0f} ms", file=sys.stderr, flush=True)
                # Collect disjoint post samples and cooldown at 2 Hz; no model runs here.
                for _ in range(60):
                    if coach.proposal is not None:
                        break
                    sample = scenario(coach.history[-1].t+.5)
                    coach.update(sample, 180-sample.t)
                if coach.proposal is None:
                    raise RuntimeError("Synthetic scenario did not produce the next eligible opportunity")
        finally:
            coach.finish(coach.history[-1].t)
            await service.close()
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Authorize real API calls with synthetic metrics")
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required to authorize real API calls with synthetic metrics")
    if not 1 <= args.trials <= 100:
        parser.error("--trials must be between 1 and 100; P3 requires at least 20")
    load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")
    if not agents.configured():
        parser.error("Configure MODEL_API_KEY in backend/.env first")
    started = time.monotonic()
    records = asyncio.run(run_batch(args.trials))
    result = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "scenario": "synthetic persistent darkness and motion, constant SQI; paired session-local decisions",
        "model": os.getenv("META_MODEL", "muse-spark-1.3"),
        "decision_deadline_seconds": ADAPTIVE_DEADLINE,
        "elapsed_seconds": round(time.monotonic()-started, 2),
        "summary": summarize(records, args.trials), "opportunities": records,
        "limitations": ["Pending requests sample synthetic metrics at wall-clock cadence; other windows are advanced.",
                        "Timeout elapsed time is censored; full provider latency and canceled-call billing are unknown.",
                        "No images or human measurements sent; no physical-camera, human-benefit or reference validation.",
                        "Report generation is covered separately; this batch measures adaptive selection and commitment."],
    }
    encoded = json.dumps(result, indent=2, allow_nan=False)+"\n"
    if args.output:
        args.output.write_text(encoded)
    print(encoded, end="")
    return 0 if result["summary"]["p3_target_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
