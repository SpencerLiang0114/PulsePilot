"""A/B/C policy evaluation on a shared synthetic trace, or exported measured reports.

Default runs use a local fixture provider and never contact Meta. Scripted traces do
not represent human responses, measure inference throughput, or establish HR accuracy.
"""
import argparse
import asyncio
import json
import math
import random
import sys
import time
import tracemalloc
from collections import Counter
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pulsepilot.coaching import MeasurementCoach
from pulsepilot.orchestration.contracts import AnalysisProposal, ClaimReference, CoachProposal
from pulsepilot.orchestration.service import OrchestrationService, as_decision
from pulsepilot.reports import build_report
from pulsepilot.schemas import DECISION_EXPLANATIONS, Analysis, CameraMetrics, Report, Sample, SessionConfig
from pulsepilot.sensing import ReliabilityGate


class FixtureProvider:
    identifier = "local-fixture-policy"

    async def propose(self, event):
        # A reproducible constrained policy, not a claim about Muse reasoning quality.
        candidate = event.context.candidates[-1]
        alternative = any(r.outcome in ("unchanged", "worsened") and r.action_id != candidate.action_id
                          for r in event.context.outcomes)
        reason = "try_alternative" if alternative else "persistent_issue"
        return CoachProposal(
            session_id=event.session_id, event_id=event.event_id, action_id=candidate.action_id,
            issue_id=candidate.issue, reason=reason, explanation=DECISION_EXPLANATIONS[reason],
        )

    async def analyze(self, event):
        return AnalysisProposal(session_id=event.session_id, event_id=event.event_id, **{
            section: [ClaimReference(claim_id=c.claim_id, claim_type=c.claim_type, evidence_id=c.evidence_id)
                      for c in event.bundle.claims if c.section == section][:4]
            for section in Analysis.model_fields
        })


def trace(seed: int) -> list[Sample]:
    rng = random.Random(seed)
    gate = ReliabilityGate()
    samples = []
    for i in range(121):
        t = i*.5
        poor = t < 40
        sqi = (.3 if poor else .8) + rng.uniform(-.015, .015)
        sample = Sample(
            t=t, sqi=sqi, fps=30,
            camera=CameraMetrics(face_visible=True, face_count=1, confidence=.98, visibility_proxy=.98,
                                 face_size=.5, brightness=25 if poor else 120, motion=.5 if poor else 0),
        )
        samples.append(gate.apply(sample, 72+rng.uniform(-1, 1), fresh_seconds=t))
    return samples


def metrics(report: Report, telemetry: list[dict]) -> dict:
    closed = [i for i in report.interventions if i.outcome != "observing"]
    completed = [i for i in closed if i.evaluated_at is not None
                 and i.evaluated_at-i.started_at >= MeasurementCoach.RESPONSE+MeasurementCoach.OBSERVE]
    comparable = [i for i in closed if i.delta is not None]
    usable_changes = [i.after_usable-i.before_usable for i in comparable
                      if i.after_usable is not None and i.before_usable is not None]
    coaching = [r for r in telemetry if r["event_type"] == "coach_request"]
    accepted = sum(r["route"] == "accepted" for r in coaching)
    rejected = sum(not r["validation"]["valid"] and r["status"] not in ("timeout", "unavailable") for r in coaching)
    ratio = lambda n, d: n/d if d else None
    return {
        "mean_sqi": report.stats.mean_sqi, "usable_fraction": report.stats.usable_fraction,
        "time_to_stable_seconds": report.stats.stable_at,
        "interventions": len(report.interventions), "intervention_completion_rate": ratio(len(completed), len(report.interventions)),
        "outcomes": dict(Counter(i.outcome for i in closed)),
        "mean_delta_sqi": mean(i.delta for i in comparable) if comparable else None,
        "mean_delta_usable": mean(usable_changes) if usable_changes else None,
        "proposal_acceptance_rate": ratio(accepted, len(coaching)),
        "invalid_proposal_rejection_rate": ratio(rejected, len(coaching)),
        "fallback_frequency": ratio(sum(r["route"] == "fallback" for r in telemetry), len(telemetry)),
        "graph_latency_ms": mean(r["graph_latency_ms"] for r in telemetry) if telemetry else None,
        "model_latency_ms": mean(r["model_latency_ms"] for r in telemetry) if telemetry else None,
        "api_requests": sum(r["usage"]["requests"] for r in telemetry) if telemetry else None,
        "input_tokens": (sum(r["usage"]["input_tokens"] or 0 for r in telemetry)
                         if any(r["usage"]["input_tokens"] is not None for r in telemetry) else None),
        "output_tokens": (sum(r["usage"]["output_tokens"] or 0 for r in telemetry)
                          if any(r["usage"]["output_tokens"] is not None for r in telemetry) else None),
        "approximate_cost_usd": None,
        "reported_capture_fps": report.stats.mean_fps,
        "reported_inference_latency_ms": report.stats.mean_latency_ms,
    }


def exported_telemetry(report: Report) -> list[dict]:
    return [{**t.model_dump(), "validation": {"valid": t.validation_result},
             "usage": {"requests": t.api_requests, "input_tokens": t.input_tokens,
                       "output_tokens": t.output_tokens}} for t in report.agent_telemetry]


async def evaluate(condition: str, samples: list[Sample]) -> dict:
    mode = {"A": "off", "B": "assist", "C": "adaptive"}[condition]
    service = OrchestrationService(mode=mode, ai_consent=True, provider=FixtureProvider())
    coach = MeasurementCoach(mode="meta" if condition == "C" else "rules")
    started, cpu = time.perf_counter(), time.process_time()
    tracemalloc.start()
    try:
        for sample in samples:
            item = coach.update(sample, 60-sample.t)
            if coach.proposal:
                context = coach.proposal
                result = await service.run_coach_event(service.coach_event(context, "select"))
                coach.resolve(context.proposal_id, as_decision(result), sample, 60-sample.t)
            elif item is not None and condition == "B":
                candidates = [c for c in coach.candidates(sample) if c.action_id == item.action_id]
                context = coach.decision_context(sample, 60-sample.t, candidates)
                result = await service.run_coach_event(service.coach_event(context, "explain", item.id))
                if result.route == "accepted":
                    item.explanation_source = "muse"
                    item.explanation = result.action.explanation
        coach.finish(samples[-1].t)
        await service.finish_measurement()
        report = build_report(SessionConfig(mode="simulation", coaching="meta"), samples, coach.interventions)
        if condition != "A":
            await service.run_report_event(service.report_event(report))
        wall, cpu_seconds = time.perf_counter()-started, time.process_time()-cpu
        _, peak = tracemalloc.get_traced_memory()
        records = list(service.telemetry.records)
        computed = metrics(report, records)
        computed["api_requests"] = 0
        return {"condition": condition, "agent_mode": mode, "source": "synthetic_fixture",
                "metrics": computed, "resources": {
                    "policy_wall_seconds": wall, "policy_cpu_seconds": cpu_seconds,
                    "peak_traced_python_bytes": peak, "policy_windows_per_second": len(samples)/wall,
                    "measurement_throughput_fps": None, "inference_performance": None,
                }, "action_sequence": [i.action_id for i in report.interventions], "telemetry": records}
    finally:
        tracemalloc.stop()
        await service.close()


async def run(args):
    trials = []
    rng = random.Random(args.seed)
    # Warm graph imports/compilation separately from the measured repeated trials.
    await evaluate("C", trace(args.seed))
    for repetition in range(args.repetitions):
        order = list("ABC")
        rng.shuffle(order)
        samples = trace(args.seed+repetition)
        for condition in order:
            trial = await evaluate(condition, [s.model_copy(deep=True) for s in samples])
            trials.append({"repetition": repetition, "order": order, **trial})
    return {"seed": args.seed, "provider": "local fixture; zero remote API requests",
            "protocol": "Same scripted trace in A/B/C; randomized order; identical 5/3/5/8 windows and gates.",
            "limits": ["Synthetic quality is independent of instructions; no simulated user response.",
                       "Policy execution timings include orchestration, not FacePhys acquisition throughput.",
                       "No physical-camera, causal benefit, or reference HR accuracy result."], "trials": trials}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reports", nargs=3, type=Path, metavar=("A", "B", "C"),
                        help="Summarize actual exported reports instead of running fixture policies")
    parser.add_argument("--input-usd-per-million", type=float, help="Operator-supplied input token price")
    parser.add_argument("--output-usd-per-million", type=float, help="Operator-supplied output token price")
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 30:
        parser.error("repetitions must be between one and thirty")
    rates = (args.input_usd_per_million, args.output_usd_per_million)
    if any(r is not None for r in rates) and not all(r is not None and math.isfinite(r) and r >= 0 for r in rates):
        parser.error("Supply both nonnegative finite token prices, or neither")
    if args.reports:
        trials = []
        for condition, path in zip("ABC", args.reports, strict=True):
            report = Report.model_validate_json(path.read_text())
            if report.agent_mode is not None and report.agent_mode != {"A": "off", "B": "assist", "C": "adaptive"}[condition]:
                parser.error(f"Report {condition} has incompatible agent_mode {report.agent_mode}")
            trials.append({"condition": condition, "source": report.mode, "agent_mode": report.agent_mode,
                           "metrics": metrics(report, exported_telemetry(report)),
                           "limits": "Missing telemetry, price inputs, or resource data remain unavailable."})
        result = {"trials": trials, "limits": "Operator must verify counterbalancing and shared measurement settings."}
    else:
        result = asyncio.run(run(args))
    if rates[0] is not None:
        result["cost_assumptions"] = {"input_usd_per_million": rates[0], "output_usd_per_million": rates[1],
                                      "limits": "Excludes unknown usage on canceled/failed requests."}
        for trial in result["trials"]:
            observed = trial["metrics"]
            if observed["input_tokens"] is not None and observed["output_tokens"] is not None:
                observed["approximate_cost_usd"] = (
                    observed["input_tokens"]*rates[0]+observed["output_tokens"]*rates[1]
                )/1_000_000
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(f"Saved {len(result['trials'])} labeled A/B/C trials to {args.output}")


if __name__ == "__main__":
    main()
