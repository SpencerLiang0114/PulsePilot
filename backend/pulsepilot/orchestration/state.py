from typing import NotRequired, TypedDict

from .contracts import (
    AnalysisProposal,
    CoachEvent,
    CoachProposal,
    GraphOutcome,
    ModelUsage,
    ReportEvent,
    ValidationResult,
)


class AgentState(TypedDict):
    # The service snapshots these trusted inputs. Nodes only return new proposal/output fields.
    event: CoachEvent | ReportEvent
    proposal: NotRequired[CoachProposal | AnalysisProposal | None]
    validation: NotRequired[ValidationResult]
    status: NotRequired[str]
    model_latency_ms: NotRequired[float]
    usage: NotRequired[ModelUsage]
    outcome: NotRequired[GraphOutcome]
