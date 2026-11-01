"""Server-authored guidance. Product gates are not clinical accuracy thresholds.

Sources checked 2026-10-29; clinical expert review remains outstanding.
No model-authored text is ever rendered, including explanations and limitations.
"""
from .schemas import GuidanceReference, HealthInsight, HealthInsightBundle, MeasurementEvidence

REFERENCES = {
    "aha_pulse": GuidanceReference(title="American Heart Association: All About Heart Rate",
        url="https://www.heart.org/en/health-topics/high-blood-pressure/the-facts-about-high-blood-pressure/all-about-heart-rate-pulse"),
    "aha_symptoms": GuidanceReference(title="American Heart Association: Heart Attack Warning Signs",
        url="https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack"),
    "cdc_activity": GuidanceReference(title="CDC: Adult Activity Overview",
        url="https://www.cdc.gov/physical-activity-basics/guidelines/adults.html"),
    "product_limits": GuidanceReference(title="PulsePilot measurement policy: unvalidated estimates; product quality gates only"),
}
URGENT_TEXT = ("You reported current chest pain, severe shortness of breath, or fainting. "
               "Seek emergency medical help now; call your local emergency number. "
               "Do not wait for this measurement or an AI response. This advice comes from your symptom report, not BPM.")


class HealthEvidenceGate:
    @staticmethod
    def assess(e: MeasurementEvidence) -> bool:
        # Only supports describing an estimate, never certifying physiological accuracy.
        return (e.source_kind not in ("simulation", "unknown")
                and e.validation_status != "unknown" and bool(e.device_name and e.measurement_method)
                and e.accepted_window_count >= 10 and e.duration >= 30
                and e.usable_fraction >= .65 and e.signal_coverage >= .65
                and e.mean_bpm is not None and 40 <= e.mean_bpm <= 180
                and e.min_bpm is not None and e.max_bpm is not None
                and 40 <= e.min_bpm <= e.mean_bpm <= e.max_bpm <= 180)


def evidence_lookup(e: MeasurementEvidence) -> dict[str, str]:
    return {
        "heart_rate": f"Accepted estimate mean {e.mean_bpm} BPM; {e.accepted_window_count} accepted windows.",
        "quality": f"Usable {e.usable_fraction:.0%}; signal coverage {e.signal_coverage:.0%}; "
                   f"duration {e.duration:g} seconds. Setup warnings: {', '.join(e.quality_warnings) or 'none'}. "
                   "Product quality thresholds do not establish clinical accuracy.",
        "source": f"Source: {e.source_kind}; device: {e.device_name}; method: {e.measurement_method}; "
                  f"validation: {e.validation_status}.",
        "context": f"Activity context: {e.activity_context} (user-declared when provided; not inferred).",
        "symptoms": "User reported concerning symptoms." if e.concerning_symptoms else "No concerning symptoms declared; symptoms were not clinically assessed.",
    }


def insight(key, category, title, text, priority, evidence, references=("product_limits",)):
    return HealthInsight(insight_id=key, category=category, title=title, text=text, priority=priority,
                         evidence_ids=list(evidence), guidance_reference_ids=list(references))


class HealthGuidanceCatalog:
    @staticmethod
    def candidates(e: MeasurementEvidence) -> list[HealthInsight]:
        candidates = []
        if e.concerning_symptoms:
            candidates.append(insight("urgent", "follow_up", "Act on your symptoms now", URGENT_TEXT,
                                      0, ("symptoms",), ("aha_symptoms",)))
        if e.source_kind == "simulation":
            return candidates + [insight("simulation", "limitation", "Synthetic demonstration only",
                "These synthetic values cannot support any personal health interpretation. Try a real measurement to explore signal quality.",
                1, ("source",))]
        if not HealthEvidenceGate.assess(e):
            setup = ("Repeat with a steady position, even lighting, and minimal movement. "
                     if e.source_kind in ("camera_rppg", "recorded_rppg") else
                     "Check the source and follow the device's measurement and signal-quality instructions before repeating. ")
            return candidates + [insight("repeat", "measurement", "Improve conditions and repeat",
                "There is insufficient evidence to interpret heart rate. " + setup +
                "A longer recording may help collect usable windows; it does not establish accuracy.",
                1, ("quality", "heart_rate", "source"))]
        candidates += [insight("estimate", "education", "What this estimate means",
            f"Accepted windows averaged {e.mean_bpm:g} BPM. BPM means beats per minute; this is an unconfirmed estimate, "
            "not a diagnosis or a measure of cardiovascular risk.", 2, ("heart_rate", "source"), ("aha_pulse", "product_limits"))]
        if e.activity_context == "resting":
            candidates.append(insight("resting", "education", "Resting context was provided",
                "You described this session as resting. Resting pulse refers to a calm, non-exercising state. "
                "This estimate cannot determine whether your heart rate is healthy.",
                3, ("context", "source"), ("aha_pulse", "product_limits")))
        candidates.append(insight("consistent", "wellness", "Keep measurement conditions consistent",
            "Use comparable, steady conditions for future measurements and note the activity context. "
            "Differences between sessions may reflect measurement effects as well as changes in pulse.",
            4, ("quality", "context")))
        if not e.concerning_symptoms:
            candidates.append(insight("activity", "wellness", "General wellness: regular activity",
                "Choose regular physical activity suited to your abilities. This general advice is not a treatment for this reading "
                "and does not promise to normalize it.", 5, (), ("cdc_activity",)))
        candidates.append(insight("follow_up", "follow_up", "Discuss persistent concerns",
            "If your pulse repeatedly seems unusual for you, discuss it with a healthcare professional. "
            "Use an appropriate reference measurement; a single result cannot establish a health condition.",
            6, ("source",), ("aha_pulse", "product_limits")))
        return candidates

    @staticmethod
    def limitations(e: MeasurementEvidence) -> list[HealthInsight]:
        validation = ("PulsePilot native measurements have no synchronized reference validation. "
                      if e.source_kind in ("camera_rppg", "recorded_rppg", "simulation") else
                      "Device provenance alone does not establish clinical validation. ")
        result = [insight("accuracy", "limitation", "Accuracy and interpretation limits",
            "Signal quality does not prove measurement accuracy or health. " + validation +
            "No diagnosis, disease-risk estimate, or medication advice is provided.",
            0, ("source", "quality", "heart_rate"))]
        if e.activity_context == "unknown":
            result.append(insight("unknown_context", "limitation", "Activity context is unknown",
                "Resting state was not established. Do not compare this result with resting-heart-rate reference ranges.",
                1, ("context",)))
        return result


def render_health_bundle(e: MeasurementEvidence, *, selected=None, status="complete", event_id=None):
    candidates = HealthGuidanceCatalog.candidates(e)
    chosen = candidates[:3] if selected is None else [next(c for c in candidates if c.insight_id == key) for key in selected]
    # Urgent advice cannot be removed or demoted by a model.
    if e.concerning_symptoms:
        chosen = [candidates[0]] + [c for c in chosen if c.insight_id != "urgent"][:2]
    limitations = HealthGuidanceCatalog.limitations(e)
    refs = {key for item in chosen + limitations for key in item.guidance_reference_ids}
    return HealthInsightBundle(report_id=e.report_id, status=status, analyst="muse" if selected is not None else "deterministic",
        insights=chosen, limitations=limitations, evidence=evidence_lookup(e),
        guidance_references={key: REFERENCES[key] for key in sorted(refs)},
        sufficient_evidence=HealthEvidenceGate.assess(e), agent_event_id=event_id)
