import { expect, test } from "@playwright/test";
import type { CoachingMode, Intervention, Report, Sample } from "../lib/types";

const sample: Sample = {
  t: 5, bpm: null, sqi: .3, usable: false, state: "Low confidence", fps: 30, latency_ms: 10,
  waveform: [], camera: {
    face_visible: true, face_count: 1, confidence: .98, center_offset: 0, face_size: .5,
    yaw_proxy: 0, roll_degrees: 0, brightness: 25, light_imbalance: 0, light_change: 0,
    motion: .5, visibility_proxy: .98, bbox: null, landmarks: [],
  },
};
const intervention: Intervention = {
  id: "intervention-1", action_id: "motion", issue: "motion",
  action: "Rest comfortably and keep your head still for the next few seconds.",
  started_at: 5.5, evaluated_at: null, before_sqi: .3, after_sqi: null, delta: null,
  before_usable: 0, after_usable: null, outcome: "observing", source: "muse",
  decision_source: "muse", explanation_source: "muse", decision_status: "selected",
  explanation: "This correction addresses a persistent observed measurement issue.",
  before_camera: {}, after_camera: {}, environmental_changes: {},
};

for (const mode of ["passive", "rules", "meta"] as CoachingMode[]) {
  test(`setup sends ${mode} coaching mode and explicit consent`, async ({ page }) => {
    let start: { coaching: CoachingMode; ai_consent: boolean } | undefined;
    await page.route("**/health", route => route.fulfill({ json: { status: "ok", ai_configured: true } }));
    await page.routeWebSocket("**/ws/measure", socket => socket.onMessage(message => {
      if (typeof message === "string") start = JSON.parse(message);
    }));
    await page.goto("/");
    await page.getByRole("button", { name: "Explore the demo" }).click();
    await page.getByLabel("Measurement coaching", { exact: true }).selectOption(mode);
    if (mode === "meta") await page.getByLabel("Let Muse Spark").check();
    await page.getByRole("button", { name: "Start simulated session" }).click();
    await expect.poll(() => start?.coaching).toBe(mode);
    expect(start?.ai_consent).toBe(mode === "meta");
  });
}

test("live decisions wait for commitment and report timeline preserves provenance", async ({ page }) => {
  let send: ((value: object) => void) | undefined;
  await page.route("**/health", route => route.fulfill({ json: { status: "ok", ai_configured: true } }));
  await page.routeWebSocket("**/ws/measure", socket => {
    send = value => socket.send(JSON.stringify(value));
    socket.onMessage(message => {
      if (typeof message === "string" && JSON.parse(message).type === "start") {
        send!({ type: "ready", ai_status: "ready" });
        send!({ type: "sample", sample, interventions: [], coaching_state: "DECIDING" });
      }
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await page.getByLabel("Let Muse Spark").check();
  await page.getByRole("button", { name: "Start simulated session" }).click();
  await expect(page.getByText("Choosing a useful adjustment…")).toBeVisible();
  await expect(page.getByText(intervention.action, { exact: true })).toHaveCount(0);
  send!({ type: "sample", sample: { ...sample, t: 5.5 }, interventions: [intervention], coaching_state: "ACTING" });
  await expect(page.getByText("Muse Spark decision", { exact: true })).toBeVisible();
  await expect(page.getByText("Time to make your adjustment")).toBeVisible();
  send!({ type: "sample", sample: { ...sample, t: 9 }, interventions: [intervention], coaching_state: "OBSERVING" });
  await expect(page.getByText("Comparing measurement conditions after your adjustment")).toBeVisible();
  const completed: Intervention = { ...intervention, evaluated_at: 13.5, after_sqi: .3, after_usable: 0, delta: 0, outcome: "unchanged" };
  const fallback: Intervention = { ...completed, id: "intervention-2", action_id: "dark", issue: "dark", action: "Face a steady light.", started_at: 22,
    evaluated_at: 30, source: "rules", decision_source: "rules", explanation_source: "rules", decision_status: "fallback_timeout", outcome: "inconclusive" };
  const statement = { kind: "limitation" as const, text: "No usable signal in this synthetic test.", evidence_ids: ["limits"] };
  const report: Report = {
    id: "coaching-timeline", created_at: "2026-10-27T04:00:00Z", mode: "simulation", analyst: "deterministic", ai_status: "unavailable",
    samples: [sample], interventions: [completed, fallback], evidence: { limits: "Synthetic scenario." }, claims: [],
    analysis: { summary: [statement], quality: [statement], interventions: [statement], recommendations: [statement] },
    stats: { mean_bpm: null, median_bpm: null, min_bpm: null, max_bpm: null, sd_bpm: null, mean_sqi: .3,
      usable_fraction: 0, tracking_fraction: 1, signal_coverage: 1, duration: 30, stable_at: null,
      mean_fps: 30, mean_latency_ms: 10, lighting_issue_fraction: 1, motion_issue_fraction: 1, alignment_issue_fraction: 0 },
  };
  send!({ type: "report", report });
  await expect(page.getByRole("heading", { name: "Guidance & observed outcomes" })).toBeVisible();
  await expect(page.getByText("Muse Spark decision", { exact: true })).toBeVisible();
  await expect(page.getByText("Rules fallback · timeout", { exact: true })).toBeVisible();
  await expect(page.getByText("Usable windows: 0% → 0%").first()).toBeVisible();
  await expect(page.getByText("inconclusive", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/coaching-timeline.png", fullPage: true });
  await page.getByRole("button", { name: "Measure", exact: true }).click();
  await expect(page.getByText(intervention.action, { exact: true })).toHaveCount(0);
  await expect(page.getByText("Muse Spark decision", { exact: true })).toHaveCount(0);
});

test("assisted explanations preserve the committed rules action and provenance", async ({ page }) => {
  let send: ((value: object) => void) | undefined;
  await page.route("**/health", route => route.fulfill({ json: { status: "ok", ai_configured: true, agent_mode: "assist" } }));
  await page.routeWebSocket("**/ws/measure", socket => {
    send = value => socket.send(JSON.stringify(value));
    socket.onMessage(message => {
      if (typeof message === "string" && JSON.parse(message).type === "start") {
        send!({ type: "ready", ai_status: "ready", agent_mode: "assist" });
        send!({ type: "sample", sample, interventions: [{ ...intervention, decision_source: "rules", source: "rules", explanation_source: "rules" }], coaching_state: "ACTING" });
      }
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await page.getByLabel("Let Muse Spark").check();
  await page.getByRole("button", { name: "Start simulated session" }).click();
  await expect(page.getByText(intervention.action, { exact: true })).toBeVisible();
  send!({ type: "sample", sample: { ...sample, t: 5.5 }, interventions: [{ ...intervention, decision_source: "rules", source: "rules" }], coaching_state: "ACTING" });
  await expect(page.getByText("Rules decision · Muse Spark explanation", { exact: true })).toBeVisible();
  await expect(page.getByText(intervention.action, { exact: true })).toBeVisible();
});

test("disabled orchestration keeps the AI consent control unavailable", async ({ page }) => {
  await page.route("**/health", route => route.fulfill({ json: { status: "ok", ai_configured: true, agent_mode: "off" } }));
  await page.goto("/");
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await expect(page.getByLabel("Let Muse Spark")).toBeDisabled();
});
