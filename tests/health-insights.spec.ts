import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import type { HealthInsightBundle, Report } from "../lib/types";

const sessionId = "health-session";
const bundle: HealthInsightBundle = {
  report_id: "health-report", agent_event_id: "health-event", graph_version: "p3.1",
  status: "pending", analyst: "deterministic", sufficient_evidence: false,
  insights: [{ insight_id: "simulation", category: "limitation", title: "Synthetic demonstration only",
    text: "Synthetic values cannot support personal health interpretation.", priority: 1,
    evidence_ids: ["source"], guidance_reference_ids: ["product"] }],
  limitations: [], evidence: { source: "Source: simulation; validation: unvalidated." },
  guidance_references: { product: { title: "PulsePilot measurement policy", url: null } },
};
const statement = { kind: "limitation" as const, text: "Fixture measurement analysis.", evidence_ids: ["limits"] };
const report: Report = {
  id: bundle.report_id, created_at: "2026-10-29T12:00:00Z", mode: "simulation", analyst: "deterministic",
  ai_status: "pending", samples: [], interventions: [], claims: [], evidence: { limits: "Fixture evidence." },
  analysis: { summary: [statement], quality: [statement], interventions: [statement], recommendations: [statement] },
  stats: { mean_bpm: null, median_bpm: null, min_bpm: null, max_bpm: null, sd_bpm: null, mean_sqi: null,
    usable_fraction: 0, tracking_fraction: 0, signal_coverage: 0, duration: 0, stable_at: null,
    mean_fps: 0, mean_latency_ms: 0, lighting_issue_fraction: 0, motion_issue_fraction: 0, alignment_issue_fraction: 0 },
  health_insights: bundle,
};

async function setup(page: Page, reportData: Report = report) {
  await page.addInitScript(() => {
    // Report protocol tests deliver a completed report immediately, independently
    // of camera permission or frame capture (covered by the freshness suite).
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      value: () => new Promise<MediaStream>(() => {}),
    });
  });
  let send!: (message: object) => void;
  let close!: () => void;
  let start: Record<string, unknown> | undefined;
  await page.route("**/health", route => route.fulfill({ json: {
    status: "ok", weights_available: true, model_ready: true, model_error: null, busy: false,
    ai_configured: true, agent_mode: "assist",
  } }));
  await page.routeWebSocket("**/ws/measure", socket => {
    send = message => socket.send(JSON.stringify(message));
    close = () => socket.close();
    socket.onMessage(message => {
      if (start) return;
      start = JSON.parse(String(message));
      send({ type: "ready", session_id: sessionId, mode: "simulation", ai_status: "ready" });
      send({ type: "report", report: reportData });
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start measurement", exact: true }).click();
  await page.getByRole("button", { name: "Enable camera & start" }).click();
  await expect(page.getByRole("heading", { name: "Health Insights", exact: true })).toBeVisible();
  return { send, close, start: () => start };
}

test("pulse variability leads the report, survives export, and fits mobile and print", async ({ page }) => {
  const result = {
    status: "available" as const, method: "BVP pulse peaks; experimental PRV, not ECG HRV",
    reason: "Longest continuous segment passing pulse-timing checks.", rmssd_ms: 100, sdnn_ms: 50.5,
    duration: 40, interval_count: 50, rejected_intervals: 2,
    interval_times: Array.from({ length: 50 }, (_, i) => 12 + i * .8),
    intervals_ms: Array.from({ length: 50 }, (_, i) => i % 2 ? 850 : 750),
  };
  const ws = await setup(page, { ...report, mode: "camera", pulse_variability: result });
  const region = page.getByRole("region", { name: "Pulse variability", exact: true });
  await expect(region.getByText("100 ms", { exact: true })).toBeVisible();
  await expect(region.getByRole("img", { name: "Pulse intervals in the analyzed continuous segment" })).toBeVisible();
  const pulseY = (await region.boundingBox())!.y;
  const healthY = (await page.getByRole("region", { name: "Health Insights" }).boundingBox())!.y;
  const summaryY = (await page.getByRole("heading", { name: "Recording summary & next measurement" }).boundingBox())!.y;
  expect(pulseY).toBeLessThan(healthY);
  expect(healthY).toBeLessThan(summaryY);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const data = JSON.parse(await readFile((await (await downloadPromise).path())!, "utf8"));
  expect(data.pulse_variability).toEqual(result);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(region.getByText("100 ms", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.emulateMedia({ media: "print" });
  await expect(region.getByRole("heading", { name: "Pulse variability", exact: true })).toBeVisible();
  await page.screenshot({ path: "/tmp/pulsepilot-variability-mobile.png", fullPage: true });
  ws.close();
});

test("reports missing variability explain the service mismatch without calling the measurement old", async ({ page }) => {
  const ws = await setup(page, { ...report, mode: "recording" });
  const region = page.getByRole("region", { name: "Pulse variability", exact: true });
  await expect(region.getByText(/average heart-rate readings cannot reconstruct HRV/)).toBeVisible();
  await expect(region.getByText(/measurement service did not include beat-to-beat analysis/)).toBeVisible();
  await expect(region.getByRole("img")).toHaveCount(0);
  ws.close();
});

function update(changes: Partial<HealthInsightBundle> = {}) {
  return { type: "health_insight", session_id: sessionId, report_id: report.id, event_id: bundle.agent_event_id,
    health_insights: { ...bundle, status: "complete", analyst: "muse", ...changes } };
}

for (const first of ["health", "analysis"]) {
  test(`independent ${first} completion preserves both results and JSON export`, async ({ page }) => {
    const ws = await setup(page);
    expect(ws.start()?.health_ai_consent).toBe(true);
    expect(ws.start()?.ai_consent).toBe(true);
    const region = page.getByRole("region", { name: "Health Insights" });
    await expect(region.getByText(/selection pending/)).toBeVisible();
    await expect(region.getByText(/Insufficient evidence/)).toBeVisible();
    const p2 = { type: "report", report: { ...report, analyst: "muse", ai_status: "complete" } };
    if (first === "health") { ws.send(update()); ws.send(p2); }
    else { ws.send(p2); ws.send(update()); }
    await expect(region.getByText(/AI-selected suggestions/)).toBeVisible();
    await expect(page.getByText("Selected by Muse Spark from server-validated session evidence")).toBeVisible();
    await region.getByText("Why this appears · evidence & guidance").click();
    await expect(region.getByText("Source: simulation; validation: unvalidated.")).toBeVisible();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export JSON" }).click();
    const data = JSON.parse(await readFile((await (await downloadPromise).path())!, "utf8"));
    expect(data.health_insights.analyst).toBe("muse");
    expect(data.health_insights.agent_event_id).toBe(bundle.agent_event_id);
    expect(data.stats).toEqual(report.stats);
    expect(data.analyst).toBe("muse");
    await page.emulateMedia({ media: "print" });
    await expect(region.getByRole("heading", { name: "Health Insights" })).toBeVisible();
    ws.close();
  });
}

test("rejects cross-session, cross-report, mismatched and duplicate results", async ({ page }) => {
  const ws = await setup(page);
  const region = page.getByRole("region", { name: "Health Insights" });
  ws.send({ ...update(), session_id: "another-session" });
  ws.send({ ...update(), report_id: "another-report" });
  ws.send({ ...update(), event_id: "another-event" });
  ws.send(update({ agent_event_id: "another-event" }));
  ws.send(update({ report_id: "another-report" }));
  await expect(region.getByText(/selection pending/)).toBeVisible();
  ws.send(update());
  await expect(region.getByText(/AI-selected suggestions/)).toBeVisible();
  ws.send(update({ status: "fallback", analyst: "deterministic" }));
  await expect(region.getByText(/AI-selected suggestions/)).toBeVisible();
});

test("failed selection retains deterministic guidance and numerical report", async ({ page }) => {
  const ws = await setup(page);
  ws.send(update({ status: "fallback", analyst: "deterministic" }));
  const region = page.getByRole("region", { name: "Health Insights" });
  await expect(region.getByText(/Showing deterministic guidance/)).toBeVisible();
  await expect(region.getByText("Synthetic values cannot support personal health interpretation.")).toBeVisible();
  await expect(page.getByText("Measurement complete", { exact: true })).toBeVisible();
});

test("disconnect ends health pending independently from completed P2", async ({ page }) => {
  const ws = await setup(page);
  ws.send({ type: "report", report: { ...report, analyst: "muse", ai_status: "complete" } });
  await expect(page.getByText("Selected by Muse Spark from server-validated session evidence")).toBeVisible();
  ws.close();
  await expect(page.getByText(/AI selection unavailable or stopped/)).toBeVisible();
  await expect(page.getByText("Selected by Muse Spark from server-validated session evidence")).toBeVisible();
});

test("late health selection updates history without navigating", async ({ page }) => {
  const ws = await setup(page);
  await page.getByRole("button", { name: "Measure", exact: true }).click();
  ws.send(update());
  await expect(page.getByRole("heading", { name: "Find your steady signal." })).toBeVisible();
  await page.getByRole("button", { name: /Session reports/ }).click();
  await page.getByRole("heading", { name: "Simulated measurement" }).click();
  await expect(page.getByText(/AI-selected suggestions/)).toBeVisible();
});

test("symptom advice appears immediately without waiting for measurement", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start measurement", exact: true }).click();
  await page.getByLabel("I am currently experiencing chest pain").check();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("Seek emergency medical help now");
  await expect(page.getByRole("dialog").getByRole("checkbox")).toHaveCount(1);
});


test("post-report errors settle pending health without replacing completed analysis", async ({ page }) => {
  const ws = await setup(page);
  ws.send({ type: "report", report: { ...report, analyst: "muse", ai_status: "complete" } });
  await expect(page.getByText("Selected by Muse Spark from server-validated session evidence")).toBeVisible();
  ws.send({ type: "error", message: "Optional report work failed." });
  await expect(page.getByText(/AI selection unavailable or stopped/)).toBeVisible();
  await expect(page.getByText("Selected by Muse Spark from server-validated session evidence")).toBeVisible();
  await expect(page.getByText("Measurement complete", { exact: true })).toBeVisible();
});

test("starting a new session settles the previous health request", async ({ page }) => {
  await setup(page);
  await page.getByRole("button", { name: "Start a new measurement" }).click();
  await page.getByRole("button", { name: /Session reports/ }).click();
  await page.getByRole("heading", { name: "Simulated measurement" }).click();
  await expect(page.getByText(/AI selection unavailable or stopped/)).toBeVisible();
  await expect(page.getByText("Synthetic values cannot support personal health interpretation.")).toBeVisible();
});
