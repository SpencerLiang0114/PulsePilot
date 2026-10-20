# Implementation plan

The shortest path is one browser session connected to one frozen FacePhys instance, then quality gating and a numerical report, then non-blocking Meta interpretation. Public availability is a separate acceptance gate.

| Phase | Deliverable | Dependencies | Acceptance criteria | Verification |
|---|---|---|---|---|
| 1. Inference | Pinned source/checkpoint, uv environment, adapter | Python 3.12, upstream weights | Warmup and finite BVP; no made-up HR for invalid input | CPU smoke, supplied recording if available |
| 2. Website | Camera/recording → socket → inference → charts → finish | Phase 1, pnpm/Next.js | Real browser frames and resource cleanup; permission errors recover | Browser interaction and socket tests |
| 3. Sensing | Pose/framing/light/motion/cadence and validity gate | Detector landmarks, timestamped frames | Invalid windows hide HR; face loss resets stable state | Numerical fixtures and protocol tests |
| 4. Meta | Coach and report workflows with strict schemas | Meta account/key | Real request with valid evidence, bounded timeout, fallback | Mock HTTP failure/schema tests plus authenticated live check |
| 5. Feedback/report | Disjoint before/after windows, four report sections, history/export | Recorded session metrics | No invented outcome; unusable sessions have no HR summary | Intervention and report tests, simulation end-to-end |
| 6. Demo | HTTPS site + WSS inference and documented evaluation | Hosting auth/resources | Camera, FacePhys, Meta, report all work through public URL | Deployed browser session; reference comparison separately |

Mandatory: real FacePhys ingestion, meaningful quality gate, deterministic guidance, closed-loop records, validated Muse integration, four report sections, failure modes, privacy consent, labeled simulation, recorded-video input, deployable artifacts.

Optional: SAM, dense mesh landmarks, accounts, durable history, multi-user GPU scaling, HRV, native apps, model training. No optional feature blocks the vertical slice.

## External gates

- No Meta credentials currently supplied; authenticate and set backend `MODEL_API_KEY` without placing it in client code.
- Vercel CLI has no authenticated account; authenticate before deployment.
- A temporary HTTPS tunnel to the local service has been established and tested. Persistent hosting remains to be chosen/provisioned.
- A real consenting-user video and synchronized reference heart-rate recording are needed for physiological accuracy evaluation.
- Upstream's checkpoint licensing notice requires author clarification before redistribution/commercial use.

Track actual executed checks in `docs/verification.md`; a planned check is not a passed check.
