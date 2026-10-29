from ..schemas import DECISION_EXPLANATIONS, Analysis, Statement
from .contracts import AnalysisProposal, CoachEvent, CoachProposal, ReportEvent, ValidationResult


def validate_action(event: CoachEvent, proposal: CoachProposal) -> ValidationResult:
    reason = None
    if (proposal.session_id, proposal.event_id) != (event.session_id, event.event_id):
        reason = "identity_mismatch"
    elif proposal.explanation != DECISION_EXPLANATIONS[proposal.reason]:
        reason = "unsupported_explanation"
    elif proposal.action_id is None:
        if proposal.reason != "wait" or proposal.issue_id is not None or event.purpose == "explain":
            reason = "invalid_abstention"
    elif (proposal.action_id not in {c.action_id for c in event.context.candidates}
          or proposal.issue_id != proposal.action_id or proposal.reason == "wait"):
        reason = "ineligible_action"
    elif proposal.action_id in ("face", "cadence"):
        reason = "deterministic_safety"
    elif proposal.reason == "try_alternative" and not any(
        r.outcome in ("unchanged", "worsened") and r.action_id != proposal.action_id
        for r in event.context.outcomes
    ):
        reason = "unsupported_outcome"
    return ValidationResult(valid=reason is None, reason=reason)


def validate_claims(event: ReportEvent, proposal: AnalysisProposal) -> ValidationResult:
    if (proposal.session_id, proposal.event_id) != (event.session_id, event.event_id):
        return ValidationResult(valid=False, reason="identity_mismatch")
    catalogue = {c.claim_id: c for c in event.bundle.claims}
    for section in Analysis.model_fields:
        selected = getattr(proposal, section)
        if len({c.claim_id for c in selected}) != len(selected):
            return ValidationResult(valid=False, reason="duplicate_claim")
        for ref in selected:
            claim = catalogue.get(ref.claim_id)
            if (claim is None or claim.section != section or claim.evidence_id != ref.evidence_id
                    or claim.claim_type != ref.claim_type
                    or ref.evidence_id not in event.bundle.evidence):
                return ValidationResult(valid=False, reason="unsupported_claim")
    return ValidationResult(valid=True)


def render_analysis(event: ReportEvent, proposal: AnalysisProposal) -> Analysis:
    catalogue = {c.claim_id: c for c in event.bundle.claims}
    return Analysis(**{section: [Statement(
        kind=catalogue[r.claim_id].statement_kind, text=catalogue[r.claim_id].text,
        evidence_ids=[catalogue[r.claim_id].evidence_id],
    ) for r in getattr(proposal, section)] for section in Analysis.model_fields})


def validate_health_insights(event, proposal):
    from ..health_guidance import HealthEvidenceGate
    from .tools import get_health_guidance
    if (proposal.session_id != event.session_id or proposal.event_id != event.event_id
            or proposal.report_id != event.evidence.report_id):
        return ValidationResult(valid=False, reason="identity_mismatch")
    candidates = {c.insight_id: c for c in get_health_guidance(event.evidence)}
    seen = set()
    for ref in proposal.selections:
        candidate = candidates.get(ref.guidance_id)
        if candidate is None or ref.guidance_id in seen:
            return ValidationResult(valid=False, reason="ineligible_guidance")
        if (ref.evidence_ids != candidate.evidence_ids
                or ref.guidance_reference_ids != candidate.guidance_reference_ids
                or not set(ref.evidence_ids) <= set(event.evidence.evidence_ids)):
            return ValidationResult(valid=False, reason="invalid_reference")
        seen.add(ref.guidance_id)
    required = "simulation" if event.evidence.source_kind == "simulation" else (
        "estimate" if HealthEvidenceGate.assess(event.evidence) else "repeat")
    if required not in seen or (event.evidence.concerning_symptoms and "urgent" not in seen):
        return ValidationResult(valid=False, reason="missing_required_guidance")
    return ValidationResult(valid=True)
