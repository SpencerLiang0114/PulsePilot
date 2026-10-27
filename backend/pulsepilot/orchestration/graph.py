"""Graph construction, with event-scoped immutable input and explicit conditional routing."""
import time
from typing import Protocol

import httpx
from langgraph.graph import END, START, StateGraph

from ..schemas import DECISION_EXPLANATIONS
from .contracts import (
    AnalysisProposal,
    CoachEvent,
    CoachProposal,
    GraphOutcome,
    ReportEvent,
    ValidatedAction,
    ValidationResult,
)
from .state import AgentState
from .validation import render_analysis, validate_action, validate_claims


class Provider(Protocol):
    identifier: str

    async def propose(self, event: CoachEvent) -> CoachProposal: ...

    async def analyze(self, event: ReportEvent) -> AnalysisProposal: ...


def build_graphs(provider: Provider):
    async def generate(state: AgentState):
        event = state["event"]
        started = time.perf_counter()
        try:
            if isinstance(event, CoachEvent):
                output = await provider.propose(event)
                proposal = CoachProposal.model_validate(output.model_dump())
            else:
                output = await provider.analyze(event)
                proposal = AnalysisProposal.model_validate(output.model_dump())
            update = {"proposal": proposal, "status": "selected"}
        except TimeoutError:
            update = {"proposal": None, "status": "timeout"}
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            update = {"proposal": None, "status": "invalid"}
        except (httpx.HTTPError, RuntimeError, ImportError):
            # Failure diagnostics are enums; provider errors may contain secrets/payloads.
            update = {"proposal": None, "status": "unavailable"}
        return {**update, "model_latency_ms": (time.perf_counter()-started)*1000}

    def validate(state: AgentState):
        event, proposal = state["event"], state.get("proposal")
        if proposal is None:
            result = ValidationResult(valid=False, reason=state["status"])
        else:
            result = validate_action(event, proposal) if isinstance(event, CoachEvent) else validate_claims(event, proposal)
        return {"validation": result, "status": state["status"] if result.valid else result.reason}

    def result(state: AgentState, route):
        event = state["event"]
        action, analysis = None, None
        if isinstance(event, CoachEvent) and route != "no_op":
            proposal = state.get("proposal") if route == "accepted" else None
            action_id = proposal.action_id if proposal else event.context.candidates[0].action_id
            reason = proposal.reason if proposal else "persistent_issue"
            action = ValidatedAction(
                session_id=event.session_id, event_id=event.event_id, proposal_id=event.context.proposal_id,
                intervention_id=event.context.intervention_id, action_id=action_id, reason=reason,
                explanation=DECISION_EXPLANATIONS[reason], source="muse" if proposal else "rules",
            )
        elif isinstance(event, ReportEvent):
            analysis = (render_analysis(event, state["proposal"]) if route == "accepted"
                        else event.bundle.baseline.model_copy(deep=True))
        return {"outcome": GraphOutcome(
            session_id=event.session_id, event_id=event.event_id, event_type=event.event_type,
            route=route, status=state.get("status", "no_eligible_action"),
            validation=state.get("validation", ValidationResult(valid=True)), action=action, analysis=analysis,
            model_latency_ms=state.get("model_latency_ms", 0.0), model_identifier=provider.identifier,
        )}

    def after_validation(state):
        return "accepted_result" if state["validation"].valid else "deterministic_fallback"

    graphs = []
    for kind in ("coach", "report"):
        graph = StateGraph(AgentState)
        graph.add_node("assess_context" if kind == "coach" else "prepare_evidence", lambda state: {})
        graph.add_node("propose_action" if kind == "coach" else "generate_analysis", generate)
        graph.add_node("validate_proposal" if kind == "coach" else "validate_claims", validate)
        graph.add_node("accepted_result", lambda state: result(state, "accepted"))
        graph.add_node("deterministic_fallback", lambda state: result(state, "fallback"))
        first = "assess_context" if kind == "coach" else "prepare_evidence"
        generate_name = "propose_action" if kind == "coach" else "generate_analysis"
        validate_name = "validate_proposal" if kind == "coach" else "validate_claims"
        graph.add_edge(START, first)
        if kind == "coach":
            graph.add_node("no_op", lambda state: result(state, "no_op"))
            graph.add_conditional_edges(first, lambda state: "propose_action" if (
                state["event"].context.candidates and state["event"].context.remaining_seconds >= 8
            ) else "no_op", {"propose_action": "propose_action", "no_op": "no_op"})
            graph.add_edge("no_op", END)
        else:
            graph.add_edge(first, generate_name)
        graph.add_edge(generate_name, validate_name)
        graph.add_conditional_edges(validate_name, after_validation,
                                    {name: name for name in ("accepted_result", "deterministic_fallback")})
        graph.add_edge("accepted_result", END)
        graph.add_edge("deterministic_fallback", END)
        graphs.append(graph.compile())
    return tuple(graphs)
