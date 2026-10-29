"""Bounded read-only projections of trusted domain data. No I/O or coach mutation."""
from ..schemas import DecisionContext, Report
from .contracts import CoachContext, EligibleAction, EvidenceBundle, QualityContext


def get_quality_context(context: DecisionContext, intervention_id: str | None = None) -> CoachContext:
    return CoachContext(
        proposal_id=context.proposal_id, sample_at=context.sample_at,
        quality=QualityContext.model_validate(context.camera), issues=context.issues.copy(),
        sqi_trend=context.sqi_trend, usable_fraction=context.usable_fraction,
        candidates=[EligibleAction.model_validate(c.model_dump(exclude={"observations"}))
                    for c in context.candidates],
        outcomes=[r.model_copy(deep=True) for r in context.outcomes[-6:]],
        remaining_seconds=context.remaining_seconds, intervention_id=intervention_id,
    )


def get_eligible_actions(context: CoachContext) -> list[EligibleAction]:
    return [c.model_copy(deep=True) for c in context.candidates]


def get_intervention_history(context: CoachContext):
    return [r.model_copy(deep=True) for r in context.outcomes]


def get_session_statistics(bundle: EvidenceBundle):
    return bundle.stats.model_copy(deep=True)


def get_report_evidence(report: Report) -> EvidenceBundle:
    return EvidenceBundle(
        report_id=report.id, stats=report.stats.model_copy(deep=True), evidence=report.evidence.copy(),
        claims=[c.model_copy(deep=True) for c in report.claims], baseline=report.analysis.model_copy(deep=True),
    )


def get_health_evidence(report):
    from ..reports import measurement_evidence
    return measurement_evidence(report)


def get_health_guidance(evidence):
    from ..health_guidance import HealthGuidanceCatalog
    return HealthGuidanceCatalog.candidates(evidence)
