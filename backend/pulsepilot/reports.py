from datetime import UTC, datetime
from statistics import mean, median, pstdev
from uuid import uuid4

from .schemas import (
    Analysis,
    GroundedClaim,
    Intervention,
    Report,
    Sample,
    SessionConfig,
    Statement,
    Statistics,
)
from .sensing import ACTIONS, issues


def statement(text: str, evidence: str, kind="fact") -> Statement:
    return Statement(kind=kind, text=text, evidence_ids=[evidence])


def build_report(config: SessionConfig, samples: list[Sample], interventions: list[Intervention]) -> Report:
    accepted = [s.bpm for s in samples if s.usable and s.bpm is not None]
    quality = [s.sqi for s in samples if s.sqi is not None]
    n = len(samples)
    fraction = lambda values: sum(values)/n if n else 0
    issue_sets = [issues(s) for s in samples]
    lighting = fraction(any(i in x for i in ("dark", "bright", "uneven", "flicker")) for x in issue_sets)
    motion = fraction("motion" in x for x in issue_sets)
    alignment = fraction(any(i in x for i in ("position", "angle", "close", "far")) for x in issue_sets)
    stats = Statistics(
        mean_bpm=round(mean(accepted), 1) if accepted else None,
        median_bpm=round(median(accepted), 1) if accepted else None,
        min_bpm=min(accepted) if accepted else None, max_bpm=max(accepted) if accepted else None,
        sd_bpm=round(pstdev(accepted), 2) if accepted else None,
        mean_sqi=round(mean(quality), 3) if quality else None,
        usable_fraction=fraction(s.usable for s in samples),
        tracking_fraction=fraction(s.camera.face_visible and s.camera.face_count == 1 for s in samples),
        signal_coverage=len(quality)/n if n else 0,
        duration=samples[-1].t if samples else 0,
        stable_at=next((s.t for s in samples if s.usable), None),
        mean_fps=round(mean(s.fps for s in samples), 1) if samples else 0,
        mean_latency_ms=round(mean(s.latency_ms for s in samples), 1) if samples else 0,
        lighting_issue_fraction=lighting, motion_issue_fraction=motion, alignment_issue_fraction=alignment,
    )
    evidence = {
        "heart_rate": (f"Accepted HR mean {stats.mean_bpm}, median {stats.median_bpm}, "
                       f"range {stats.min_bpm}–{stats.max_bpm} BPM; {len(accepted)} accepted windows.")
                      if accepted else "No usable heart-rate windows; no average or range can be reported.",
        "quality": (f"Mean periodicity SQI {stats.mean_sqi}; usable {stats.usable_fraction:.1%}; "
                    f"signal coverage {stats.signal_coverage:.1%}. SQI is not an accuracy probability."),
        "camera": (f"Single-face tracking {stats.tracking_fraction:.1%}; lighting issues {lighting:.1%}; "
                   f"motion issues {motion:.1%}; alignment issues {alignment:.1%}. "
                   "Visibility and pose use six-landmark proxies, not full occlusion detection."),
        "timing": f"Mean processed capture rate {stats.mean_fps} fps; mean pipeline latency {stats.mean_latency_ms} ms.",
        "limits": "No synchronized reference device. No claim of physiological accuracy, diagnosis, or causal intervention benefit.",
        "interventions": f"{len(interventions)} interventions; before/after association does not establish causation.",
        "mode": f"Source is {config.mode}. Simulation data are synthetic and are not physiological measurements.",
    }
    summary = [statement(
        "Only windows that passed the signal and camera checks contribute to this summary. "
        "The observed range describes estimates during this session, not a diagnosis."
        if accepted else
        "There was not enough usable signal to report a heart rate. Improve the setup and repeat the measurement.",
        "heart_rate")]
    valid = [s for s in samples if s.usable and s.bpm is not None]
    change = None
    if len(valid) >= 10:
        half = len(valid)//2
        change = mean(s.bpm for s in valid[half:])-mean(s.bpm for s in valid[:half])
        evidence["trend"] = (f"Second-half minus first-half accepted mean HR: {change:.1f} BPM. "
                             "Only accepted windows included; no reference-based physiological interpretation.")
        summary.append(statement(
            "The estimates were fairly consistent between the early and late usable windows."
            if abs(change) < 5 else
            "The estimates changed between early and late usable windows. This alone cannot separate a pulse change from measurement effects.",
            "trend"))
    quality_text = ("Most windows passed the measurement checks. That indicates usable signal conditions, "
                    "but does not establish accuracy against a reference device."
                    if stats.usable_fraction >= 0.65 else
                    "A substantial part of the session did not pass the measurement checks. "
                    "Those estimates were excluded from the heart-rate summary.")
    quality_sections = [statement(quality_text, "quality")]
    if lighting > 0.1 or motion > 0.1:
        quality_sections.append(statement(
            "Lighting changes or movement occurred during this session and may have contributed to unstable estimates. "
            "The observations do not establish a physiological cause.", "camera", "possible explanation"))
    intervention_sections = []
    for item in interventions:
        evidence[item.id] = (
            f"Action: {item.action} Start {item.started_at:.1f}s. "
            f"Pre SQI {item.before_sqi}, post SQI {item.after_sqi}, change {item.delta}. "
            f"Pre usable {item.before_usable}, post usable {item.after_usable}. Outcome {item.outcome}. "
            f"Decision {item.decision_source} ({item.decision_status}); explanation {item.explanation_source}. "
            f"Observed environmental changes {item.environmental_changes}."
        )
        text = {
            "improved": "Signal periodicity increased after this instruction. The comparison shows an association, not improved accuracy.",
            "worsened": "Signal periodicity decreased after this instruction. Other changes during the comparison may have contributed.",
            "unchanged": "Signal periodicity did not change enough to meet the improvement threshold after this instruction.",
            "inconclusive": "There was not enough comparable signal before and after this instruction to determine its effect.",
            "observing": "This intervention was still being observed when measurement ended.",
        }[item.outcome]
        if len(intervention_sections) < 4:
            intervention_sections.append(statement(f"{item.action} {text}", item.id))
    if not intervention_sections:
        intervention_sections = [statement("No corrective intervention was completed in this session.", "interventions")]
    recommendations = []
    for condition, action in ((lighting > 0.1, "uneven"), (motion > 0.1, "motion"), (alignment > 0.1, "angle")):
        if condition:
            recommendations.append(statement(ACTIONS[action], "camera", "possible explanation"))
    if stats.usable_fraction < 0.65:
        recommendations.append(statement("Repeat or extend the measurement after the setup is steady.", "quality", "limitation"))
    if not recommendations:
        recommendations.append(statement("Use the same steady, evenly lit setup for a future measurement.", "camera", "possible explanation"))
    recommendations = recommendations[:3] + [statement(
        "These estimates are for research and personal observation. A high-quality signal is not a substitute for reference measurement.",
        "limits", "limitation")]
    analysis = Analysis(summary=summary, quality=quality_sections,
                        interventions=intervention_sections, recommendations=recommendations)
    facts = {
        "heart_rate": ("measurement", "mean_bpm", stats.mean_bpm),
        "trend": ("measurement", "accepted_half_change_bpm", change),
        "quality": ("quality", "usable_fraction", stats.usable_fraction),
        "camera": ("quality", "largest_camera_issue_fraction", max(lighting, motion, alignment)),
        "interventions": ("outcome", "intervention_count", float(len(interventions))),
        "limits": ("limitation", "reference_validation", "unavailable"),
        **{item.id: ("outcome", "outcome", item.outcome) for item in interventions},
    }
    claims = []
    for section in type(analysis).model_fields:
        for index, item in enumerate(getattr(analysis, section)):
            ref = item.evidence_ids[0]
            kind, metric, value = facts[ref]
            if item.kind == "limitation":
                kind = "limitation"
            claim_type = ("measurement_recommendation" if section == "recommendations" else
                          "measurement_limitation" if ref == "limits" else
                          "signal_available" if ref == "heart_rate" and accepted else
                          "signal_unavailable" if ref == "heart_rate" else
                          "accepted_estimate_trend" if ref == "trend" else
                          f"intervention_{value}" if ref.startswith("intervention-") else
                          "intervention_count" if ref == "interventions" else "quality_limitation")
            claims.append(GroundedClaim(
                claim_id=f"{section}-{index}", claim_type=claim_type, section=section, kind=kind, evidence_id=ref,
                metric=metric, value=value, text=item.text, statement_kind=item.kind,
            ))
    return Report(
        id=str(uuid4()), created_at=datetime.now(UTC).isoformat(), mode=config.mode, stats=stats,
        samples=[s.model_copy(update={"waveform": [], "waveform_times": []}) for s in samples],
        interventions=[i.model_copy(deep=True) for i in interventions], evidence=evidence,
        analysis=analysis, claims=claims,
    )
