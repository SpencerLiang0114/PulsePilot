# PulsePilot hackathon roadmap: P3–P7

Plan written October 28, 2026. Phase status and verification are recorded below; the remaining phases are proposed work. Implement them in order, using each exit criterion to decide whether to proceed.

## Starting point and objective

P1/P2 already provide FacePhys sensing, deterministic reliability gates, intervention outcome tracking, session-local history, typed LangGraph workflows, provenance, and report export. The recorded automated checks pass, but both recorded live Muse coaching calls timed out. Physical-camera performance, human benefit, and durable deployment remain unverified. See [verification](verification.md).

The submission objective is a working measurement assistant: detect a poor capture condition, select an adjustment, observe the person's response, measure the result, and use that result in the next decision. Target the “Push the Frontier” problem statement. Explain the benefit for researchers collecting webcam pulse data; keep outputs about measurement conditions and avoid medical advice.

Before implementation, document which capabilities predate the event and which were actually developed during it. Git history supports that account but commit dates alone do not establish creation dates. Resolve the checkpoint rights question described in [FacePhys integration](facephys-integration.md#licensing-limitation) before relying on redistributed weights or public hosting. The participant guide requires a public repository, a three-minute demo, and clearly identified new work.

Preserve throughout: independent frame processing, deterministic BPM acceptance, explicit consent, session isolation, truthful source attribution, and cancellation on finish/disconnect. Do not relax these to obtain a successful demo.

## P3 — Reliable live Meta decisions

**Goal:** Make adaptive action selection work repeatedly with the real provider.

**Status (October 28):** Implemented; the declared twenty-opportunity live synthetic batch passed with twenty validated Muse commitments and later accepted outcome feedback. See [P3 implementation and verification](p3-live-decisions.md). Physical-camera performance and human benefit remain unverified.

### Scope

1. Extend the existing live verification script to run repeated, explicitly opted-in trials with synthetic metrics. Include multiple eligible actions and subsequent decisions receiving measured outcome history.
2. Record accepted selections, valid abstentions, invalid responses, timeouts, and end-to-end latency. Distinguish a provider response from an action actually committed by the coach. Report timeout frequency separately; canceled requests do not reveal full provider latency.
3. Investigate avoidable latency. Evaluate reusing an HTTP client with correct lifecycle cleanup, and reduce redundant prompt/schema payload only where contracts remain intact.
4. If the 1.5-second deadline remains impractical, implement a bounded slower planning window for adaptive choices. Keep immediate deterministic corrections, recheck current eligibility and context freshness at commitment, and discard obsolete results. Update all relevant service, coach, and UI timing assumptions together.
5. Retain deterministic fallback and exact provenance in every failure path.

**Likely files:** `backend/pulsepilot/agents.py`, `backend/pulsepilot/orchestration/{provider,service}.py`, `backend/pulsepilot/{app,coaching}.py`, `scripts/verify_sensing_agent.py`, relevant backend tests.

**Exit criterion:** In a declared test batch of at least 20 eligible live decision opportunities, target at least 90% validated outcomes within the chosen budget; count valid abstentions separately from selected actions. Demonstrate repeated actual Muse-selected commitments and a later accepted decision receiving previous outcomes. This is a proposed engineering target, not an existing result or evidence of user benefit.

**Verification:** Tests for delayed valid output, resolved issues, stale context, face loss, disconnect, mode/consent boundaries, and uninterrupted frame acknowledgements. Save the full batch summary, including failures and limitations. If the target is missed, keep P3 incomplete and investigate before advertising reliable adaptive control.

## P4 — Repeatable real-camera measurement

**Goal:** Complete a real-person session reliably from camera permission to exported report.

### Scope

1. Exercise the actual webcam with a consenting person under stable lighting, reduced lighting, motion, and recovery. Start with the developer's own camera.
2. Measure actual capture/inference cadence, sample freshness, tracking continuity, accepted-signal fraction, and time to first stable signal. Keep model-only throughput separate.
3. Fix observed capture, warmup, transport, or lifecycle failures. Make loading and unavailable-signal states understandable. Preserve rejection rules rather than adjusting thresholds to make numbers appear.
4. Verify that finish/restart releases the single inference slot and that losing the face removes stale BPM immediately.

**Likely files:** `lib/use-measurement.ts`, `components/pulsepilot.tsx`, `backend/pulsepilot/{app,estimator,sensing}.py`, existing browser/protocol tests. Change only the parts implicated by observed failures.

**Exit criterion:** Three consecutive real-camera sessions complete and export successfully on the declared demo hardware. Controlled degradation and recovery are visible, unavailable signal is represented honestly, and restart works without restarting the backend. Record actual results; do not imply reference-device accuracy.

**Verification:** Real-camera manual record plus targeted regression tests for any bugs found. Synthetic browser tests remain useful but do not satisfy this phase's exit criterion.

## P5 — Make the agent's work visible

**Goal:** Let a viewer understand the complete intervention loop within a short demonstration.

### Scope

1. Inspect the existing live state/provenance panel and report timeline before adding UI. Reuse them wherever possible.
2. Make the current problem, committed instruction, action source, observation period, and measured outcome easy to follow.
3. Show before/after quality and usability with units and explicit unavailable/inconclusive states. Show prior outcome context only when it is supported by the recorded decision reason and evidence.
4. Clearly distinguish Muse selection, rules selection, assisted explanation, and fallback. Avoid exposing internal event IDs or raw telemetry in the main flow.
5. Preserve the same evidence in the exported report. Keep the heatmap described as model attention.

**Likely files:** `components/pulsepilot.tsx`, `components/report.tsx`, `lib/types.ts`, `lib/use-measurement.ts`; backend contracts only if necessary evidence is genuinely absent.

**Exit criterion:** In one recorded run, a viewer can identify the problem, who selected the adjustment, what happened afterward, and how a subsequent decision relates to the history. The presentation also handles an unsuccessful or inconclusive intervention honestly.

**Verification:** Targeted browser checks for source attribution, outcome states, and export consistency, plus visual review of the actual demonstration viewport. Read the installed Next.js guidance before implementation.

## P6 — Small real-user evaluation

**Goal:** Establish what the completed system does in practice and where it fails.

### Scope

1. Follow the existing [evaluation protocol](evaluation.md). Compare rules (`off`) with adaptive (`adaptive`); add assisted (`assist`) only if time permits.
2. Recruit 3–5 consenting volunteers if practical. Alternate/counterbalance mode order and keep hardware, session length, and condition scripts consistent. Record deviations and failed runs.
3. Export every session and summarize with the existing evaluation tooling. Report usable fraction, time to stable signal, intervention completion/outcomes, and model selection/fallback counts, including per-person results.
4. Describe results as an exploratory pilot. A before/after improvement does not establish causality, and increased SQI does not establish HR accuracy. Omit reference accuracy claims unless synchronized reference measurements are actually collected.
5. If volunteers are unavailable, publish the narrower self-test scope and leave multi-user benefit unverified.

**Likely files:** `scripts/evaluate_p2.py` only where aggregation is missing, `docs/evaluation.md`, a dated results summary. Keep identifying participant data and recordings out of the public repository.

**Exit criterion:** Produce an auditable summary with sample size, conditions, all outcomes, missing data, and limitations. A null or negative comparison is a valid evaluation result; do not tune the study to manufacture an advantage.

**Verification:** Reconcile summary counts and statistics with exported reports. Inspect failure cases before deciding what the demo and pitch may claim.

## P7 — Hosted demo and submission

**Goal:** Deliver a reproducible public project and an accessible three-minute demonstration.

### Scope

1. Use the existing [deployment runbook](deployment.md) to host a persistent inference backend and HTTPS frontend. Verify checkpoint permissions first. Disclose the one-real-session capacity limit and make busy behavior understandable.
2. Test from a second device: permission, warmup, measurement, model selection/fallback, finish, export, disconnect, and restart. Keep credentials server-only and require session consent.
3. Prepare a contribution inventory distinguishing pre-event sensing/UI from work actually built during the event. Preserve original history and third-party attribution.
4. Record the video: approximately 20 seconds for the user/problem, 100 seconds for the live intervention loop, 40 seconds for measured evidence and Meta's role, and 20 seconds for new contributions and limitations. Label any simulated or replayed segment.
5. Check repository visibility, setup instructions, deployment access, video access, and contributor list. Review public files/exports for credentials and participant data before publishing.

**Exit criterion:** Another person can access the product or clearly labeled fallback demo, open the video and repository, and understand exactly what was newly built and verified. Complete the submission form with those artifacts.

**Verification:** Fresh-browser checks of all links, final relevant automated checks, and one complete hosted real-camera session. Local build success alone is insufficient.

## Suggested schedule and scope cuts

| Dates (Eastern) | Focus |
|---|---|
| October 28–29 | P3: live-provider reliability |
| October 29–30 | P4: physical-camera reliability |
| October 30–31 | P5: visible intervention loop |
| November 1–2 | P6: evaluation and evidence |
| November 2–3 | P7: deployment, video, submission preparation |
| November 4 | Buffer and submission before 9 PM Eastern |

This is a proposed schedule, not a delivery guarantee. Start deployment feasibility and rights checks early because they can block P7. See the local [participant guide](../meta_hack_description.md) and [official event page](https://dev.meta.ai/events/global-hackathon) for requirements and deadline updates.

If time slips, cut additional models, SAM integration, accounts, databases, persistent personal memory, broad UI redesign, and the optional assisted evaluation condition. Preserve real-provider evidence, real-camera checks, truthful contribution boundaries, and the submission artifacts. If P3 cannot deliver reliable adaptive selection, demonstrate the assisted/report capability that actually works and explicitly narrow the claim.
