# Agents and closed-loop feedback

## Verified Meta interface

Meta lists `muse-spark-1.3` through its [Model API](https://dev.meta.ai/docs/models). Use server-only `MODEL_API_KEY` and `https://api.meta.ai/v1/chat/completions`. The [structured-output cookbook](https://dev.meta.ai/docs/cookbook/structured-output) documents `response_format: {type: "json_schema", json_schema: {name, strict, schema}}`. Pydantic validates responses again; reject unknown fields, invalid evidence identifiers, and instructions outside the deterministic eligible set.

The user explicitly requested Python orchestration and Meta models. Python calls the documented HTTPS endpoint directly. Credentials stay in ignored `backend/.env`; no key is sent to the browser. P1 uses only Meta. The other supplied hackathon credentials are stored locally and are not used by this loop. `httpx[socks]` supports the development machine's configured proxy.

Requests use the documented [`reasoning_effort: "minimal"`](https://dev.meta.ai/docs/reasoning) to fit interactive decisions. Authenticated structured decisions and a complete synthetic closed loop have been verified; see [the saved live run](p1-live-verification.json). This is a software integration check, not a physical-camera or reference-device validation.

## MeasurementCoach

`candidate_actions()` in `sensing.py` derives structured candidates from current issues, with an action ID, fixed instruction, triggering scalar observations, and priority. Each issue must persist independently for five seconds. Simultaneous darkness and motion therefore produce independently selectable candidates. No candidate is produced for a stable setup. Missing/multiple faces and invalid cadence are handled by deterministic policy, ahead of other corrections. Existing estimator weights, capture/inference cadence, reliability thresholds and BPM acceptance rules are unchanged.

The coach takes a five-second baseline immediately before issuing an instruction, allows three seconds to respond, and collects a disjoint five-second post window. Window metrics require at least eight samples spanning at least three and a half seconds; SQI comparisons additionally require eight nonmissing SQI values. An outcome needs a SQI change of at least eight percentage points to be classified as improved or worsened. Missing comparable signal or an interrupted session is inconclusive. Every intervention stores pre/post SQI, usable fractions, averaged scalar camera metrics and observed environmental changes. An eight-second cooldown prevents overlapping comparisons. These are before/after associations, without claims of accuracy or causal benefit.

Use separate enter/exit quality thresholds for stable state. Immediately hide HR when face/cadence validity fails. No intervention when no important issue exists.

## Asynchronous decision state machine

```text
MONITORING → DECIDING → ACTING → OBSERVING → COOLDOWN → MONITORING
                 └─ valid abstention ────────→ COOLDOWN
```

`MeasurementCoach.update()` proposes a `DecisionContext` without creating an intervention. It contains scalar camera metrics, current issues, recent SQI trend, usable fraction, candidates, up to six completed outcomes, remaining session duration and the decision deadline. It contains no frames, bounding boxes, landmarks, waveform, or API credentials.

The WebSocket session starts at most one `SensingDecisionAgent.decide()` task. Camera processing and samples continue. A two-second wall-clock deadline covers the complete request. The strict `AgentDecision` contains a candidate `action_id` (or null), a reason, and a bounded explanation. Explanations must exactly match one of the server-supplied supported explanations. An alternative-action explanation additionally requires an actual unsuccessful prior action. This prevents fabricated observations or outcomes in coaching text while leaving action selection to Muse.

On the next fresh sample, the coach rechecks the proposal ID, active session, current eligibility, safety conditions and remaining observation time before committing. Instruction timing starts at this commitment. No new request or intervention overlaps the active one. Resolved actions are discarded; face loss/multiple faces invalidate pending requests, including between sample events. Sample gaps invalidate pending proposals and make active comparisons inconclusive. Finish, disconnect, errors and cancellation cancel/drain pending tasks before session cleanup. Task completion itself cannot mutate the coach or send an instruction.

Timeouts, authentication/network failures, malformed output and ineligible decisions use the current eligible deterministic candidate. Provenance records `decision_source`, `explanation_source`, and `decision_status` (`selected`, `rules`, `safety`, or `fallback_*`). The legacy `source` field mirrors `decision_source`. A fallback never acquires Muse decision provenance. Valid abstention creates no intervention and waits through a cooldown. No instruction starts if insufficient time remains for the response and observation windows.

## Session-local outcome memory

`OutcomeMemory` stores up to six completed summaries. The next request receives actual outcomes and environmental changes. Unchanged/worsened actions are suppressed while the same issue and relevant observations remain materially unchanged, allowing another eligible action instead. A resolved issue or a material change in its triggering metrics permits a later retry. Inconclusive results do not count as failures. Previously improved candidates receive preference in the deterministic fallback ordering. Safety instructions remain eligible. The memory is recreated for every session; there is no training, persistent profiling or model-weight update.

The setup dialog exposes `passive`, `rules`, and `meta`. AI requests require explicit AI consent and a configured key. Without them, Meta mode uses deterministic coaching. Passive mode produces no interventions; rules mode makes no decision requests. Separately consented report interpretation may still run in either mode. The live panel exposes the current state and decision source; report timelines preserve instruction and evaluation times, pre/post metrics, outcomes and fallback reasons.

## ReportAnalyst

The server computes accepted-HR mean, median, range, trend points, observed duration, valid proportion, tracking continuity, camera-condition summaries, time to stable signal, cadence, latency, and intervention comparisons. Numerical data and conclusions remain immutable.

`build_report()` creates a typed `GroundedClaim` catalogue for the four sections. Each claim binds a section, claim/evidence IDs, claim type, statement type, metric, exact value and deterministic text. Muse selects complete claims from this catalogue; it does not author factual prose. `analyze_report()` validates the strict schema, exact equality of every field, section placement and absence of duplicate claims, then renders the canonical server text. Altered numbers, fabricated improvement, unsupported stable/accurate-heart-rate claims, medical text, causal claims and fabricated observations are rejected. This is deliberately more restrictive than validating evidence IDs or prohibited phrases.

On any invalid or unavailable response, the complete deterministic report and statistics are preserved with `ai_status: "unavailable"`. The numerical report is delivered before the optional analysis request. The UI always renders numerical statistics from deterministic tools. Claims and decision/explanation provenance are included in exported JSON.

## Reproducible verification

```sh
cd backend
uv run pytest -q
RUN_FACEPHYS_INTEGRATION=1 uv run pytest -q tests/test_facephys_integration.py
uv run python ../scripts/smoke_facephys.py
# Opt-in real Meta requests, explicitly synthetic conditions:
uv run python ../scripts/verify_sensing_agent.py --live --output ../docs/p1-live-verification.json
```

`test_sensing_agent.py` covers persistent multiple candidates, selection/abstention, unsupported explanations, timeouts/auth failures, fallback provenance, disjoint windows, adaptation, stale/late results, finish/disconnect/restart cleanup, consent and a complete WebSocket loop. Browser tests cover mode selection, explicit consent, pending-versus-committed instructions, state visibility and report provenance. See [P1 validation](p1-verification.md) for results and limits.

## SAM decision

[SAM 3.1](https://dev.meta.ai/docs/sam/overview) supports text-prompt image/video segmentation via `POST /v1/responses`, with streaming boxes/masks. Access requires a Meta API key; segmentation is not a face-pose or rPPG-quality API. Its latency, expense, extra facial-image transfer, and uncertain skin-mask benefit do not justify inclusion in the first slice. Existing six-point detector landmarks support approximate alignment and visibility now. Dense landmarks are a later upgrade.

Optional experiment: with explicit image-transfer consent, compare SAM skin/occlusion visibility against lightweight landmarks on annotated clips. Measure detection correctness, latency, and downstream usability. Never change the FacePhys crop/mask without an independent ablation and reference validation.
