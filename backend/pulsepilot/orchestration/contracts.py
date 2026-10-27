from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..schemas import (
    Analysis,
    ClaimType,
    DecisionReason,
    GroundedClaim,
    OutcomeRecord,
    Statistics,
)
from ..sensing import ACTIONS

GRAPH_VERSION = "p2.1"
AgentMode = Literal["off", "observe", "assist", "adaptive"]
ActionID = Literal[
    "face", "visibility", "position", "far", "close", "angle", "dark", "bright",
    "uneven", "flicker", "motion", "cadence", "signal",
]
Identity = Annotated[str, Field(pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class QualityContext(Contract):
    face_visible: bool
    face_count: float = Field(ge=0)
    confidence: float
    center_offset: float
    face_size: float
    yaw_proxy: float
    roll_degrees: float
    brightness: float
    light_imbalance: float
    light_change: float
    motion: float
    visibility_proxy: float
    fps: float
    sqi: float | None = None


class EligibleAction(Contract):
    action_id: ActionID
    issue: ActionID
    instruction: str
    priority: int = Field(ge=0)

    @model_validator(mode="after")
    def canonical(self):
        if self.issue != self.action_id or self.instruction != ACTIONS[self.action_id]:
            raise ValueError("Action must match the deterministic catalogue")
        return self


class CoachContext(Contract):
    proposal_id: int = Field(ge=1)
    sample_at: float = Field(ge=0)
    quality: QualityContext
    issues: list[ActionID] = Field(max_length=13)
    sqi_trend: float | None
    usable_fraction: float = Field(ge=0, le=1)
    candidates: list[EligibleAction] = Field(max_length=13)
    outcomes: list[OutcomeRecord] = Field(max_length=6)
    remaining_seconds: float = Field(ge=0)
    intervention_id: str | None = None

    @model_validator(mode="after")
    def eligible(self):
        ids = [c.action_id for c in self.candidates]
        if len(ids) != len(set(ids)) or not set(ids) <= set(self.issues):
            raise ValueError("Candidates must be unique observed issues")
        return self


class EvidenceBundle(Contract):
    report_id: Identity
    stats: Statistics
    evidence: dict[str, str] = Field(max_length=64)
    claims: list[GroundedClaim] = Field(max_length=32)
    baseline: Analysis

    @model_validator(mode="after")
    def references(self):
        ids = [c.claim_id for c in self.claims]
        if len(ids) != len(set(ids)) or any(c.evidence_id not in self.evidence for c in self.claims):
            raise ValueError("Invalid evidence catalogue")
        return self


class Event(Contract):
    session_id: Identity
    event_id: Identity
    issued_at: float = Field(ge=0)
    measurement_timestamp: float = Field(ge=0)
    ai_consent: bool
    graph_version: Literal["p2.1"] = GRAPH_VERSION


class CoachEvent(Event):
    event_type: Literal["coach_request"] = "coach_request"
    purpose: Literal["select", "explain", "observe"]
    context: CoachContext

    @model_validator(mode="after")
    def timestamp(self):
        if self.measurement_timestamp != self.context.sample_at:
            raise ValueError("Measurement timestamp must match context")
        if self.purpose == "explain" and self.context.intervention_id is None:
            raise ValueError("Explanation requires a committed intervention")
        if self.purpose == "explain" and len(self.context.candidates) != 1:
            raise ValueError("Explanation must identify exactly one committed action")
        if self.purpose == "select" and self.context.intervention_id is not None:
            raise ValueError("Selection must precede commitment")
        return self


class ReportEvent(Event):
    event_type: Literal["report_request"] = "report_request"
    bundle: EvidenceBundle


class CoachProposal(Contract):
    session_id: Identity
    event_id: Identity
    action_id: ActionID | None
    issue_id: ActionID | None
    reason: DecisionReason
    explanation: str = Field(min_length=1, max_length=240)


class ClaimReference(Contract):
    claim_id: str = Field(min_length=1, max_length=80)
    evidence_id: str = Field(min_length=1, max_length=80)
    claim_type: ClaimType


class AnalysisProposal(Contract):
    session_id: Identity
    event_id: Identity
    summary: list[ClaimReference] = Field(min_length=1, max_length=4)
    quality: list[ClaimReference] = Field(min_length=1, max_length=4)
    interventions: list[ClaimReference] = Field(min_length=1, max_length=4)
    recommendations: list[ClaimReference] = Field(min_length=1, max_length=4)


class ValidationResult(Contract):
    valid: bool
    reason: str | None = None


class ValidatedAction(Contract):
    session_id: Identity
    event_id: Identity
    proposal_id: int
    intervention_id: str | None
    action_id: ActionID | None
    reason: DecisionReason
    explanation: str
    source: Literal["rules", "muse"]


class ModelUsage(Contract):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    requests: int = Field(default=0, ge=0)


class GraphOutcome(Contract):
    session_id: Identity
    event_id: Identity
    event_type: Literal["coach_request", "report_request"]
    graph_version: str = GRAPH_VERSION
    route: Literal["accepted", "fallback", "no_op", "discarded", "disabled"]
    status: str
    validation: ValidationResult
    action: ValidatedAction | None = None
    analysis: Analysis | None = None
    model_latency_ms: float = 0.0
    graph_latency_ms: float = 0.0
    model_identifier: str | None = None
    usage: ModelUsage = Field(default_factory=ModelUsage)
