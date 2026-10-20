import { expect, test } from "@playwright/test";
import type { Report } from "../lib/types";

function pendingReport(): Report {
  const statement = { kind: "limitation" as const, text: "No usable signal in this synthetic test.", evidence_ids: ["limits"] };
  return {
    id: "pending-ai-test", created_at: "2026-10-20T12:00:00Z", mode: "simulation",
    analyst: "deterministic", ai_status: "pending", samples: [], interventions: [],
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
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await page.getByRole("button", { name: "Start simulated session" }).click();
  await expect(page.getByText("Numerical report ready.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Measure", exact: true }).click();
  sendUpdate!();
  await expect(page.getByRole("heading", { name: "Find your steady signal." })).toBeVisible();
  await page.getByRole("button", { name: /Session reports/ }).click();
  await page.getByRole("heading", { name: "Simulated measurement" }).click();
  await expect(page.getByText("Interpreted by Muse Spark from this session’s evidence")).toBeVisible();
});

test("starting over marks an unfinished AI interpretation as stopped", async ({ page }) => {
  await page.routeWebSocket("**/ws/measure", socket => {
    socket.onMessage(() => socket.send(JSON.stringify({ type: "report", report: pendingReport() })));
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await page.getByRole("button", { name: "Start simulated session" }).click();
  await expect(page.getByText("Numerical report ready.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Start a new measurement" }).click();
  await page.getByRole("button", { name: /Session reports/ }).click();
  await page.getByRole("heading", { name: "Simulated measurement" }).click();
  await expect(page.getByText("AI interpretation was stopped.", { exact: false })).toBeVisible();
});
