import asyncio
import os
import time
from uuid import uuid4

from langsmith import tracing_context

from ..schemas import DECISION_EXPLANATIONS, AgentDecision, DecisionContext, DecisionResult, Report
from ..timing import ADAPTIVE_DEADLINE, COACH_DEADLINE
from .contracts import (
    AgentMode,
    CoachEvent,
    GraphOutcome,
    HealthInsightEvent,
    ReportEvent,
    ValidatedAction,
    ValidationResult,
)
from .graph import build_graphs
from .health_graph import build_health_graph, health_outcome
from .provider import MetaProvider, invocation_usage, read_usage
from .telemetry import Telemetry
from .tools import get_health_evidence, get_quality_context, get_report_evidence

REPORT_DEADLINE = 12.0
HEALTH_DEADLINE = 12.0


def configured_mode() -> AgentMode:
    value = os.getenv("AGENT_MODE", "assist").strip().lower()
    if value not in ("off", "observe", "assist", "adaptive"):
        raise ValueError("AGENT_MODE must be off, observe, assist, or adaptive")
    return value


def fallback(event: CoachEvent | ReportEvent | HealthInsightEvent, status: str, route="fallback") -> GraphOutcome:
    if isinstance(event, HealthInsightEvent):
        return health_outcome(event, status, route=route)
    action, analysis = None, None
    if route == "fallback":
        if isinstance(event, CoachEvent) and event.context.candidates:
            action = ValidatedAction(
                session_id=event.session_id, event_id=event.event_id,
                proposal_id=event.context.proposal_id, intervention_id=event.context.intervention_id,
                action_id=event.context.candidates[0].action_id, source="rules", reason="persistent_issue",
                explanation=DECISION_EXPLANATIONS["persistent_issue"],
            )
        elif isinstance(event, ReportEvent):
            analysis = event.bundle.baseline.model_copy(deep=True)
    return GraphOutcome(
        session_id=event.session_id, event_id=event.event_id, event_type=event.event_type,
        route=route, status=status, validation=ValidationResult(valid=False, reason=status),
        action=action, analysis=analysis,
    )


def as_decision(outcome: GraphOutcome) -> DecisionResult:
    if outcome.route == "accepted" and outcome.action is not None:
        return DecisionResult(status="selected", decision=AgentDecision(
            action_id=outcome.action.action_id, reason=outcome.action.reason,
            explanation=outcome.action.explanation,
        ))
    return DecisionResult(status=outcome.status if outcome.status in ("timeout", "unavailable") else "invalid")


class OrchestrationService:
    """One service per WebSocket. Results never mutate the coach or send UI events."""

    def __init__(self, *, session_id=None, mode: AgentMode | None = None, ai_consent=False, health_ai_consent=False, provider=None):
        self.session_id = session_id or str(uuid4())
        self.mode = mode if mode is not None else configured_mode()
        if self.mode not in ("off", "observe", "assist", "adaptive"):
            raise ValueError("Unknown agent mode")
        self.ai_consent = ai_consent
        self.health_ai_consent = health_ai_consent
        self._owns_provider = provider is None
        self.provider = provider if provider is not None else MetaProvider()
        self.telemetry = Telemetry()
        self._graphs = None
        self._health_graph = None
        self._seen: set[str] = set()
        self._running: dict[str, tuple[str, asyncio.Task]] = {}
        self.closed = False
        self.measuring = True

    def coach_event(self, context: DecisionContext, purpose, intervention_id=None):
        return CoachEvent(
            session_id=self.session_id, event_id=str(uuid4()), issued_at=time.monotonic(),
            measurement_timestamp=context.sample_at, ai_consent=self.ai_consent, purpose=purpose,
            context=get_quality_context(context, intervention_id),
        )

    def report_event(self, report: Report):
        return ReportEvent(
            session_id=self.session_id, event_id=str(uuid4()), issued_at=time.monotonic(),
            measurement_timestamp=report.stats.duration, ai_consent=self.ai_consent,
            bundle=get_report_evidence(report),
        )

    def health_insight_event(self, report: Report):
        return HealthInsightEvent(
            session_id=self.session_id, event_id=str(uuid4()), issued_at=time.monotonic(),
            measurement_timestamp=report.stats.duration, ai_consent=self.health_ai_consent,
            evidence=get_health_evidence(report),
        )

    async def run_health_insight_event(self, event: HealthInsightEvent) -> GraphOutcome:
        return await self._run(event, 2, HEALTH_DEADLINE)

    async def run_coach_event(self, event: CoachEvent) -> GraphOutcome:
        return await self._run(event, 0, ADAPTIVE_DEADLINE if event.purpose == "select" else COACH_DEADLINE)

    async def run_report_event(self, event: ReportEvent) -> GraphOutcome:
        return await self._run(event, 1, REPORT_DEADLINE)

    async def _run(self, event, graph_index, deadline):
        # Revalidate and deep-snapshot all nested domain models, including model_copy inputs.
        event = type(event).model_validate(event.model_dump(), strict=True)
        if self.closed or event.session_id != self.session_id or (graph_index == 0 and not self.measuring):
            return fallback(event, "inactive_session", "discarded")
        if event.event_id in self._seen:
            return fallback(event, "duplicate_event", "discarded")
        if len(self._seen) >= 512:
            return fallback(event, "event_limit", "discarded")
        self._seen.add(event.event_id)
        age = time.monotonic()-event.issued_at
        if age < -0.01 or age >= deadline:
            return fallback(event, "stale_event", "discarded")
        if self.mode == "off":
            return fallback(event, "off", "disabled")
        if isinstance(event, CoachEvent) and (
            (self.mode == "assist" and event.purpose != "explain")
            or (self.mode == "observe" and event.purpose != "observe")
        ):
            return fallback(event, "mode_restricted", "discarded")
        consent = self.health_ai_consent if isinstance(event, HealthInsightEvent) else self.ai_consent
        event = event.model_copy(update={"ai_consent": consent and event.ai_consent})
        started = time.perf_counter()
        usage = {"requests": 0}
        token = invocation_usage.set(usage)
        self._running[event.event_id] = (event.event_type, asyncio.current_task())
        try:
            # Disable external tracing even when a parent process has tracing environment variables.
            with tracing_context(enabled=False):
                try:
                    async with asyncio.timeout(deadline-age):
                        if graph_index == 2:
                            if self._health_graph is None:
                                self._health_graph = build_health_graph(self.provider)
                            graph = self._health_graph
                        else:
                            if self._graphs is None:
                                self._graphs = build_graphs(self.provider)
                            graph = self._graphs[graph_index]
                        state = await graph.ainvoke({"event": event})
                        outcome = state["outcome"]
                except TimeoutError:
                    outcome = fallback(event, "timeout")
            if self.closed or (graph_index == 0 and not self.measuring):
                outcome = fallback(event, "inactive_session", "discarded")
            elif time.monotonic()-event.issued_at >= deadline:
                outcome = fallback(event, "timeout")
            elapsed = (time.perf_counter()-started)*1000
            outcome = outcome.model_copy(update={
                "graph_latency_ms": elapsed, "usage": read_usage(usage),
                "model_identifier": self.provider.identifier,
                "model_latency_ms": outcome.model_latency_ms or (elapsed if usage["requests"] else 0.0),
            })
            self.telemetry.record(outcome)
            if isinstance(event, HealthInsightEvent) and self.mode == "observe" and outcome.route != "discarded":
                outcome = outcome.model_copy(update={"health_insights": health_outcome(event, "observed").health_insights})
            return outcome
        finally:
            self._running.pop(event.event_id, None)
            invocation_usage.reset(token)

    async def finish_measurement(self):
        self.measuring = False
        tasks = [task for kind, task in list(self._running.values()) if kind == "coach_request"]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        self.closed = True
        tasks = [task for _, task in list(self._running.values())]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self._owns_provider:
            await self.provider.close()
