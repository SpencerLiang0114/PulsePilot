# Health-aware report interpretation (P3 Core)

Implemented for native PulsePilot reports. `HealthInsightAgent` is the independent LangGraph workflow compiled by `build_health_graph`; it selects server-authored guidance rather than generating health advice. The P2 coaching/report graphs, estimator, accepted samples, ReliabilityGate, and `Analysis` contract are unchanged. Hardware ingestion is a separate, unimplemented milestone.

## Contracts and trust boundary

`build_report()` always includes a deterministic `health_insights` bundle. `measurement_evidence()` projects the server-owned report into a frozen `MeasurementEvidence` snapshot with immutable tuple fields. It includes accepted statistics, accepted-window count, duration, quality, source/method, validation status, and structured user-declared context. Preliminary report windows never enter accepted statistics. No WebSocket message accepts uploaded statistics, source descriptions, or external reports.

Native source mappings are `camera → camera_rppg`, `recording → recorded_rppg`, and `simulation → simulation`. All native measurements are explicitly unvalidated. A source label such as wearable PPG would not establish clinical validation. The evidence contract accommodates other sources, but does not authorize importing them.

The start message adds two optional fields (old clients default to no health transfer):

```json
{
  "health_ai_consent": false,
  "health_context": {
    "activity": "unknown",
    "concerning_symptoms": false
  }
}
```

Activity is `resting`, `active`, `recovery`, or `unknown`. The current UI offers an optional resting declaration and otherwise preserves unknown context. For a recording, this declaration describes the recording's measurement conditions. The symptom checkbox describes **current** chest pain, severe shortness of breath, or fainting; it is not inferred from the recording or estimates. Unchecked does not mean symptoms have been clinically ruled out. No free-text health history is collected.

`HealthInsightBundle` contains report/event identity, status, analyst, at most three insights, mandatory limitations, a measurement evidence dictionary, source-reference metadata, evidence sufficiency, and graph version `p3.1`. Each insight contains its catalogue identity, category, server-authored title/text, priority, evidence IDs, and guidance-reference IDs. General wellness education can have no measurement evidence; its source references remain required.

## Evidence and guidance policy

The deterministic `HealthEvidenceGate` permits a description of an accepted estimate only with a documented real source/method, documented validation status (including explicitly unvalidated), at least 10 accepted windows, at least 30 seconds, usable fraction and signal coverage at least 0.65, and internally consistent mean/min/max within the existing product's 40–180 BPM range. These are conservative **product eligibility checks**, not clinically validated accuracy thresholds. Overlapping windows are not independent physiological observations. These rules do not establish that the underlying heart rate is correct.

Simulation always gets synthetic-data limitations. Missing/poor/short/unknown-source evidence gets measurement-improvement advice without personal physiological interpretation. Unknown activity always gets a resting-context limitation. Native measurements always show the lack of reference validation. Resting education requires an explicit user declaration; no normal/abnormal classification or numerical resting-range comparison is implemented. Age, fitness, medication, and clinical history are not available.

The server catalogue includes estimate education, consistent measurement conditions, general physical activity education, repeat-measurement guidance, and bounded professional follow-up for persistent concerns. It never diagnoses, estimates disease risk, prescribes, recommends medication changes, or certifies health. General activity guidance is excluded when concerning symptoms are declared.

Current symptom reports trigger urgent advice deterministically, independently of simulation, data quality, consent, agent mode, and provider availability. The setup dialog displays it immediately, before measurement; the report includes it first. A proposal that omits it is rejected, and rendering always places it first. This is symptom-directed guidance, not automatic emergency detection from a camera.

Sources checked against their published guidance on 2026-10-29:

- [American Heart Association: All About Heart Rate](https://www.heart.org/en/health-topics/high-blood-pressure/the-facts-about-high-blood-pressure/all-about-heart-rate-pulse) — BPM definition, activity context, professional follow-up.
- [American Heart Association: Heart Attack Warning Signs](https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack) — urgent symptom guidance.
- [CDC: Adult Activity Overview](https://www.cdc.gov/physical-activity-basics/guidelines/adults.html) — general physical activity education; no personalized exercise prescription.
- PulsePilot product policy — source validation limits, setup guidance, and product evidence gates. This is explicitly labeled as product policy, not an authoritative clinical standard.

**Review status:** the templates were checked against these sources during implementation. They have not been reviewed or approved by a clinician. Source attribution and automated policy tests are not expert review.

## Release scope (2026-11-01)

Pulse variability is removed from the release: no pulse-interval analysis, RMSSD, SDNN, variability report section, exported variability result, or variability-based Health Insight is generated. Reports retain accepted heart-rate estimates, signal quality, Health Insights, and measurement guidance.

## Graph and lifecycle

The seven named nodes are `prepare_health_evidence`, `assess_evidence_quality`, `build_guidance_candidates`, `generate_health_insights`, `validate_health_insights`, `render_health_insights`, and `health_fallback` (the final two are alternative branches). The graph lives in its own module and typed state, leaving P2's two-graph return contract intact.

Muse receives only identity, normalized evidence, and eligible server-authored candidates. `HealthInsightProposal` permits identity and one to three selections containing guidance/evidence/reference IDs. Strict schemas forbid additional text. Validation requires exact session, event, and report identities; unique eligible guidance; exact corresponding evidence/source references; and inclusion of the applicable estimate, simulation, or repeat guidance. Required symptom advice cannot be omitted. Model output never becomes user-visible prose.

The service uses a separate 12-second health deadline (the HTTP adapter also has a 10-second network-call cap). P3 does not use the coaching deadline. `off` is deterministic; `observe` evaluates consented proposals but preserves deterministic displayed guidance; `assist` and `adaptive` can publish validated selections. Health consent is independent of frame consent and P2 AI consent. P2's evidence projection excludes the newly added health context. There is no image transfer to Muse, persistent health history, or new third-party service.

The WebSocket sends the numerical report and deterministic health guidance first. A pending bundle identifies the forthcoming health event. P2 and P3 then run concurrently; neither waits for the other. P2 retains its existing `report` update. P3 publishes:

```json
{
  "type": "health_insight",
  "session_id": "original-session-uuid",
  "report_id": "original-report-uuid",
  "event_id": "original-health-event-uuid",
  "health_insights": { "report_id": "original-report-uuid", "agent_event_id": "original-health-event-uuid" }
}
```

(The bundle is abbreviated above.) The service rejects inactive, stale, duplicate, or cross-session events. The frontend accepts health results only for the current socket generation, matching session/report/event, and an outstanding pending bundle; duplicate results are ignored. Late P2 snapshots cannot regress completed health insights. Navigation does not force users back to the report. New measurement/reset/disconnect cancels outstanding work; disconnected pending health results become unavailable while retaining deterministic guidance and completed P2 results. Finishing sensing cancels coaching and releases inference capacity before report-time work starts.

Health content is excluded from agent telemetry. Metadata records the health event kind and graph version. JSON export includes the final health bundle and context. Print includes the displayed guidance and limitations; expandable evidence follows the existing report print behavior (hidden in print, retained in JSON).

## Evaluation

Automated fixtures are in `test_health_insights.py`, `test_graph_health.py`, `test_health_protocol.py`, and `tests/health-insights.spec.ts`.

| Area | Evidence | Boundary |
|---|---|---|
| Software correctness | Full backend suite, TypeScript, production build, browser suite; consent matrix, identity checks, timeout/cancellation, concurrent P2/P3 delivery in both orders, export, navigation | Fixture tests do not establish live Muse latency or real physiological accuracy |
| Guidance policy | Real/synthetic, missing/poor/short data, unknown activity with elevated BPM, low user-declared resting BPM, symptoms; invented/duplicate/mismatched/ineligible selections rejected | Automated checks verify this catalogue and validator, not clinical appropriateness across all users |
| External reports | Forged device instructions and conflicting source reports rejected at the session input schema | There is no external adapter or source reconciliation; these are negative ingestion tests |
| Expert review | No expert-reviewed examples supplied or created | Clinical review and evaluation against clinician-labeled examples remain outstanding |
| Real-world accuracy | No new human/reference-device measurements | No accuracy, clinical validation, or physiological benefit claim |

Verification recorded on 2026-10-29:

- Full backend suite: **248 passed, 2 skipped**. The skipped tests require `RUN_FACEPHYS_INTEGRATION=1`; they are not counted as passes.
- Focused new health evidence/graph/WebSocket suite: **47 passed** after the final source-aware guidance edits.
- Full Playwright suite: **38 passed**, including real FacePhys processing of synthetic recording/camera frames. One pre-existing camera assertion was narrowed to the measurement-state element because the same label appears in three places.
- TypeScript check, production build, Ruff, and whitespace checks passed.
- The report screenshot was visually inspected for the separate Health Insights section. Browser tests verify export, print visibility, independent result ordering, missing consent, stale identities, cancellation, and post-report errors.
- No live Muse request or human/reference-device experiment was performed. Provider selections and failures in tests use controlled fixtures.

Reproduce from the repository root:

```sh
pnpm check
pnpm build
uv run --project backend pytest -q backend/tests
uv run --directory backend ruff check pulsepilot tests ../scripts
# Start frontend/backend with MODEL_API_KEY empty, then:
pnpm test:e2e
```

Before claiming clinical review, have a qualified reviewer assess the actual catalogue and labeled examples (especially symptom wording, age/fitness limitations, abstention, and follow-up). Record reviewer identity/qualifications, date, example labels, disagreements, and resulting changes. This implementation does not fabricate that review.

M1–M4 and automated M5 coverage are implemented. Expert-reviewed evaluation within M5 remains outstanding. M6 JSON/CSV hardware adapters, vendor SDKs, Bluetooth, PDF ingestion, persistent health profiles, and medical-record integration remain separate work.
