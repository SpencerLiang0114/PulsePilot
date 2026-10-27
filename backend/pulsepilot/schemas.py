from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictStr


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class SessionConfig(StrictModel):
    type: Literal["start"] = "start"
    mode: Literal["camera", "recording", "simulation"] = "camera"
    duration: int = Field(default=60, ge=30, le=180)
    frame_consent: bool = False
    ai_consent: bool = False
    coaching: Literal["passive", "rules", "meta"] = "meta"


class SessionCommand(StrictModel):
    type: Literal["finish", "extend"]


class CameraMetrics(StrictModel):
    face_visible: bool = False
    face_count: int = 0
    confidence: float = 0
    center_offset: float = 0
    face_size: float = 0
    yaw_proxy: float = 0
    roll_degrees: float = 0
    brightness: float = 0
    light_imbalance: float = 0
    light_change: float = 0
    motion: float = 0
    visibility_proxy: float = 0
    bbox: list[float] | None = None
    landmarks: list[list[float]] = Field(default_factory=list)


class Sample(StrictModel):
    t: float
    bpm: float | None = None
    sqi: float | None = None
    usable: bool = False
    state: str = "Measuring"
    fps: float = 0
    latency_ms: float = 0
    camera: CameraMetrics = Field(default_factory=CameraMetrics)
    waveform: list[float] = Field(default_factory=list)
    waveform_times: list[float] = Field(default_factory=list)


class FaceHeatmap(StrictModel):
    t: float
    bbox: list[float] = Field(min_length=4, max_length=4)
    pulse: float = Field(default=0.5, ge=0, le=1)
    width: Literal[36] = 36
    height: Literal[36] = 36
    values: list[int] = Field(min_length=1296, max_length=1296)


CoachingState = Literal["MONITORING", "DECIDING", "ACTING", "OBSERVING", "COOLDOWN"]
DecisionReason = Literal["persistent_issue", "try_alternative", "wait"]
DECISION_EXPLANATIONS = {
    "persistent_issue": "This correction addresses a persistent observed measurement issue.",
    "try_alternative": "A previous correction did not improve periodicity; try another eligible correction.",
    "wait": "Wait for more evidence before another correction.",
}


class CandidateAction(StrictModel):
    action_id: str
    issue: str
    instruction: str
    observations: dict[str, float | bool]
    priority: int


class OutcomeRecord(StrictModel):
    action_id: str
    decision_source: Literal["rules", "muse"]
    outcome: Literal["improved", "unchanged", "worsened", "inconclusive"]
    before_sqi: float | None
    after_sqi: float | None
    before_usable: float | None
    after_usable: float | None
    environmental_changes: dict[str, float]


class DecisionContext(StrictModel):
    proposal_id: int
    sample_at: float
    camera: dict[str, float | bool]
    issues: list[str]
    sqi: float | None
    sqi_trend: float | None
    usable_fraction: float
    candidates: list[CandidateAction]
    outcomes: list[OutcomeRecord]
    remaining_seconds: float
    deadline_seconds: float = 1.5


class AgentDecision(StrictModel):
    action_id: str | None
    # The model chooses a supported reason; the server renders its explanation.
    reason: DecisionReason
    explanation: str = Field(min_length=1, max_length=240)


class DecisionResult(StrictModel):
    decision: AgentDecision | None = None
    status: Literal["selected", "timeout", "invalid", "unavailable"]


class Intervention(StrictModel):
    id: str
    issue: str
    action: str
    started_at: float
    evaluated_at: float | None = None
    before_sqi: float | None = None
    after_sqi: float | None = None
    delta: float | None = None
    before_usable: float | None = None
    after_usable: float | None = None
    outcome: Literal["observing", "improved", "unchanged", "worsened", "inconclusive"] = "observing"
    source: Literal["rules", "muse"] = "rules"
    explanation: str | None = None
    action_id: str = ""
    decision_source: Literal["rules", "muse"] = "rules"
    explanation_source: Literal["rules", "muse"] = "rules"
    decision_status: str = "rules"
    agent_event_id: str | None = None
    graph_version: str | None = None
    model_latency_ms: float | None = None
    graph_latency_ms: float | None = None
    before_camera: dict[str, float] = Field(default_factory=dict)
    after_camera: dict[str, float] = Field(default_factory=dict)
    environmental_changes: dict[str, float] = Field(default_factory=dict)


class Statement(StrictModel):
    kind: Literal["fact", "possible explanation", "limitation"]
    text: str = Field(min_length=1, max_length=600)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class Analysis(StrictModel):
    summary: list[Statement] = Field(min_length=1, max_length=4)
    quality: list[Statement] = Field(min_length=1, max_length=4)
    interventions: list[Statement] = Field(min_length=1, max_length=4)
    recommendations: list[Statement] = Field(min_length=1, max_length=4)


ClaimType = Literal[
    "signal_available", "signal_unavailable", "mean_bpm_observed", "accepted_estimate_trend",
    "tracking_continuity", "quality_limitation", "measurement_limitation", "measurement_recommendation",
    "intervention_improved", "intervention_unchanged", "intervention_worsened", "intervention_inconclusive",
    "intervention_observing", "intervention_count",
]


class GroundedClaim(StrictModel):
    claim_id: str
    claim_type: ClaimType
    section: Literal["summary", "quality", "interventions", "recommendations"]
    kind: Literal["measurement", "quality", "outcome", "limitation"]
    statement_kind: Literal["fact", "possible explanation", "limitation"]
    evidence_id: str
    metric: str
    value: StrictFloat | StrictStr | None
    text: str = Field(min_length=1, max_length=900)


class ReportInterpretation(StrictModel):
    summary: list[GroundedClaim] = Field(min_length=1, max_length=4)
    quality: list[GroundedClaim] = Field(min_length=1, max_length=4)
    interventions: list[GroundedClaim] = Field(min_length=1, max_length=4)
    recommendations: list[GroundedClaim] = Field(min_length=1, max_length=4)


class Statistics(StrictModel):
    mean_bpm: float | None
    median_bpm: float | None
    min_bpm: float | None
    max_bpm: float | None
    sd_bpm: float | None
    mean_sqi: float | None
    usable_fraction: float
    tracking_fraction: float
    signal_coverage: float
    duration: float
    stable_at: float | None
    mean_fps: float
    mean_latency_ms: float
    lighting_issue_fraction: float
    motion_issue_fraction: float
    alignment_issue_fraction: float


class Report(StrictModel):
    id: str
    created_at: str
    mode: Literal["camera", "recording", "simulation"]
    stats: Statistics
    samples: list[Sample]
    interventions: list[Intervention]
    evidence: dict[str, str]
    analysis: Analysis
    analyst: Literal["deterministic", "muse"] = "deterministic"
    ai_status: str = "not_configured"
    claims: list[GroundedClaim] = Field(default_factory=list)
    agent_event_id: str | None = None
    graph_version: str | None = None
