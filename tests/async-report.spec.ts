import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import type { Report, Sample } from "../lib/types";

function pendingReport(): Report {
  const statement = { kind: "limitation" as const, text: "No usable signal in this synthetic test.", evidence_ids: ["limits"] };
  return {
    id: "pending-ai-test", created_at: "2026-10-20T12:00:00Z", mode: "simulation",
    analyst: "deterministic", ai_status: "pending", samples: [], interventions: [], claims: [],
    evidence: { limits: "Synthetic test of asynchronous report lifecycle." },
    analysis: { summary: [statement], quality: [statement], interventions: [statement], recommendations: [statement] },
    stats: {
      mean_bpm: null, median_bpm: null, min_bpm: null, max_bpm: null, sd_bpm: null, mean_sqi: null,
      usable_fraction: 0, tracking_fraction: 0, signal_coverage: 0, duration: 0, stable_at: null,
      mean_fps: 0, mean_latency_ms: 0, lighting_issue_fraction: 0, motion_issue_fraction: 0,
      alignment_issue_fraction: 0,
    },
  };
}

test("late AI interpretation updates history without navigating away", async ({ page }) => {
  let sendUpdate: (() => void) | undefined;
  await page.routeWebSocket("**/ws/measure", socket => {
    socket.onMessage(() => socket.send(JSON.stringify({ type: "report", report: pendingReport() })));
    sendUpdate = () => socket.send(JSON.stringify({
      type: "report", report: { ...pendingReport(), ai_status: "complete", analyst: "muse" },
    }));
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start measurement", exact: true }).click();
  await page.getByRole("button", { name: "Enable camera & start" }).click();
  await expect(page.getByText("Numerical report ready.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Measure", exact: true }).click();
  sendUpdate!();
  await expect(page.getByRole("heading", { name: "Find your steady signal." })).toBeVisible();
  await page.getByRole("button", { name: /Session reports/ }).click();
  await page.getByRole("heading", { name: "Simulated measurement" }).click();
  await expect(page.getByText("Selected by Muse Spark from server-validated session evidence")).toBeVisible();
});

const trendSample: Sample = {
  t: 10, bpm: null, report_bpm: null, sqi: .4, usable: false, state: "Low confidence",
  fps: 30, latency_ms: 10, waveform: [], camera: {
    face_visible: true, face_count: 1, confidence: .98, center_offset: 0, face_size: .5,
    yaw_proxy: 0, roll_degrees: 0, brightness: 140, light_imbalance: 0, light_change: 0,
    motion: 0, visibility_proxy: .98, bbox: null, landmarks: [],
  },
};

for (const width of [1440, 390]) {
  test(`report distinguishes preliminary estimates and preserves gaps at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1080 });
    const report: Report = { ...pendingReport(), ai_status: "disabled", samples: [
      { ...trendSample, bpm: 70, usable: true },
      { ...trendSample, t: 10.5 },
      { ...trendSample, t: 11, report_bpm: 92 },
      { ...trendSample, t: 11.5 },
      { ...trendSample, t: 13, bpm: 74, usable: true },
      // Legacy exports may contain an unusable candidate; it must not be plotted as accepted.
      { ...trendSample, t: 13.5, bpm: 999 },
    ] };
    report.stats = { ...report.stats, mean_bpm: 72, min_bpm: 70, max_bpm: 74, duration: 13.5 };
    await page.routeWebSocket("**/ws/measure", socket => {
      socket.onMessage(() => socket.send(JSON.stringify({ type: "report", report })));
    });
    await page.goto("/");
    await page.getByRole("button", { name: "Start measurement", exact: true }).click();
    await page.getByRole("button", { name: "Enable camera & start" }).click();
    const chart = page.getByRole("img", { name: "Accepted and preliminary heart-rate estimates over the session" });
    await expect(chart.locator('[data-series="Accepted"] circle')).toHaveCount(2);
    await expect(chart.locator('[data-series="Preliminary"] circle')).toHaveCount(1);
    const path = await chart.locator('[data-series="Accepted"] path').getAttribute("d");
    expect(path?.match(/M/g)).toHaveLength(2);
    expect(path).not.toContain("L");
    await expect(page.getByText("2 accepted · 1 preliminary windows.", { exact: false })).toBeVisible();
    await expect(page.locator(".report-main-number")).toContainText("72");
    await expect(page.getByRole("heading", { name: "Session report", exact: true })).toBeVisible();
    const qualityHeading = page.getByRole("heading", { name: "Measurement quality", exact: true });
    await expect(qualityHeading).toBeVisible();
    for (const title of ["Pulse variability", "Recording summary & next measurement", "Measurement timeline", "Health Insights", "Measurement quality & guidance details", "Technical capture details"]) {
      const heading = page.getByRole("heading", { name: title, exact: true });
      await expect(heading).toBeVisible();
      const section = heading.locator("../..");
      await expect(section.locator(":scope > header > p")).toBeVisible();
      await expect(section.locator(":scope > .panel")).toBeVisible();
      await expect(section.locator(":scope > details")).toHaveCount(0);
    }
    await chart.locator('[data-series="Preliminary"] circle').hover();
    await expect(page.locator(".chart-tooltip")).toContainText("92.0 BPM · Preliminary");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const downloaded = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export JSON" }).click();
    const download = await downloaded;
    const data = JSON.parse(await readFile((await download.path())!, "utf8"));
    expect(data.samples[2].report_bpm).toBe(92);
    expect(data.samples[2].usable).toBe(false);
    expect(data.stats.mean_bpm).toBe(72);
    await page.screenshot({ path: `test-results/report-trend-${width}.png`, fullPage: true });
    await page.emulateMedia({ media: "print" });
    await expect(chart).toBeVisible();
    await expect(qualityHeading).toBeVisible();
    await expect(page.getByText("○ Preliminary · amber, dashed")).toBeVisible();
  });
}

test("a single preliminary estimate is visible without an accepted summary", async ({ page }) => {
  const report = { ...pendingReport(), ai_status: "disabled", samples: [{ ...trendSample, report_bpm: 88 }] };
  await page.routeWebSocket("**/ws/measure", socket => {
    socket.onMessage(() => socket.send(JSON.stringify({ type: "report", report })));
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start measurement", exact: true }).click();
  await page.getByRole("button", { name: "Enable camera & start" }).click();
  await expect(page.getByText("Insufficient usable signal", { exact: true })).toBeVisible();
  await expect(page.locator('[data-series="Preliminary"] circle')).toHaveCount(1);
  await expect(page.getByText("No heart-rate windows passed the report checks")).toHaveCount(0);
});

test("starting over marks an unfinished AI interpretation as stopped", async ({ page }) => {
  await page.routeWebSocket("**/ws/measure", socket => {
    socket.onMessage(() => socket.send(JSON.stringify({ type: "report", report: pendingReport() })));
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start measurement", exact: true }).click();
  await page.getByRole("button", { name: "Enable camera & start" }).click();
  await expect(page.getByText("Numerical report ready.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Start a new measurement" }).click();
  await page.getByRole("button", { name: /Session reports/ }).click();
  await page.getByRole("heading", { name: "Simulated measurement" }).click();
  await expect(page.getByText("AI interpretation was stopped.", { exact: false })).toBeVisible();
});
