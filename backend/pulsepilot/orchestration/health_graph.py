"""Independent completed-report graph; never receives frames or estimator access."""
import time
from itertools import pairwise
from typing import NotRequired, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from ..health_guidance import HealthEvidenceGate, render_health_bundle
from ..schemas import HealthInsight, MeasurementEvidence
from .contracts import GraphOutcome, HealthInsightEvent, HealthInsightProposal, ValidationResult
from .tools import get_health_guidance
from .validation import validate_health_insights


class HealthState(TypedDict):
    event: HealthInsightEvent
    evidence: NotRequired[MeasurementEvidence]
    sufficient: NotRequired[bool]
    candidates: NotRequired[list[HealthInsight]]
    proposal: NotRequired[HealthInsightProposal | None]
    validation: NotRequired[ValidationResult]
    status: NotRequired[str]
    model_latency_ms: NotRequired[float]
    outcome: NotRequired[GraphOutcome]


def health_outcome(event, status, *, proposal=None, route="fallback", latency=0.0):
    return GraphOutcome(session_id=event.session_id, event_id=event.event_id,
        event_type=event.event_type, graph_version=event.graph_version, route=route, status=status,
        validation=ValidationResult(valid=proposal is not None, reason=None if proposal else status),
        health_insights=render_health_bundle(event.evidence,
            selected=[r.guidance_id for r in proposal.selections] if proposal else None,
            status="complete" if proposal else "not_requested" if status in ("off", "not_requested", "observed") else "fallback",
            event_id=event.event_id), model_latency_ms=latency)


def build_health_graph(provider):
    async def generate(state):
        event = state["event"]
        if not event.ai_consent:
            return {"proposal": None, "status": "not_requested", "model_latency_ms": 0.0}
        began = time.perf_counter()
        try:
            output = await provider.health_insights(event)
            proposal = HealthInsightProposal.model_validate(output.model_dump())
            status = "selected"
        except (TimeoutError, httpx.TimeoutException):
            proposal, status = None, "timeout"
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            proposal, status = None, "invalid"
        except (httpx.HTTPError, RuntimeError, ImportError):
            proposal, status = None, "unavailable"
        return {"proposal": proposal, "status": status, "model_latency_ms": (time.perf_counter()-began)*1000}

    def validate(state):
        validation = (validate_health_insights(state["event"], state["proposal"]) if state["proposal"]
                      else ValidationResult(valid=False, reason=state["status"]))
        return {"validation": validation, "status": state["status"] if validation.valid else validation.reason}

    def render(state, accepted):
        return {"outcome": health_outcome(state["event"], state["status"],
            proposal=state["proposal"] if accepted else None, route="accepted" if accepted else "fallback",
            latency=state["model_latency_ms"])}

    graph = StateGraph(HealthState)
    graph.add_node("prepare_health_evidence", lambda s: {"evidence": s["event"].evidence})
    graph.add_node("assess_evidence_quality", lambda s: {"sufficient": HealthEvidenceGate.assess(s["evidence"])})
    graph.add_node("build_guidance_candidates", lambda s: {"candidates": get_health_guidance(s["evidence"])})
    graph.add_node("generate_health_insights", generate)
    graph.add_node("validate_health_insights", validate)
    graph.add_node("render_health_insights", lambda s: render(s, True))
    graph.add_node("health_fallback", lambda s: render(s, False))
    nodes = [START, "prepare_health_evidence", "assess_evidence_quality", "build_guidance_candidates",
             "generate_health_insights", "validate_health_insights"]
    for first, second in pairwise(nodes):
        graph.add_edge(first, second)
    graph.add_conditional_edges("validate_health_insights", lambda s:
        "render_health_insights" if s["validation"].valid else "health_fallback",
        {name: name for name in ("render_health_insights", "health_fallback")})
    graph.add_edge("render_health_insights", END)
    graph.add_edge("health_fallback", END)
    return graph.compile()
