import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("desktop simulation completes, preserves evidence, exports, and keeps history", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Find your steady signal." })).toBeVisible();
  await page.screenshot({ path: "test-results/desktop.png", fullPage: true });
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel("Let Muse Spark")).toBeDisabled();
  await page.getByRole("button", { name: "Start simulated session" }).click();
  await expect(page.getByText("Simulation · 4× playback")).toBeVisible();
  await expect(page.getByRole("button", { name: "Finish", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "30 sec", exact: true }).click();
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuemax", "90");
  await expect(page.getByText("Measurement complete", { exact: true })).toBeVisible({ timeout: 40000 });
  await expect(page.getByText("Simulated session", { exact: true })).toBeVisible();
  await expect(page.getByText("Evidence-based deterministic analysis. Muse Spark was not used.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "What changed with guidance" })).toBeVisible();
  await page.screenshot({ path: "test-results/report.png", fullPage: true });
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const download = await downloaded;
  const data = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(data.mode).toBe("simulation");
  expect(data.analyst).toBe("deterministic");
  expect(data.interventions.length).toBeGreaterThanOrEqual(2);
  expect(data.stats.mean_bpm).toBeGreaterThan(65);
  expect(data.samples.some((s: { bpm: number | null }) => s.bpm === null)).toBe(true);
  await page.getByRole("button", { name: "All reports" }).click();
  await expect(page.getByRole("heading", { name: "Simulated measurement" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("a user-selected recording runs through FacePhys and finishes at end of video", async ({ page }) => {
  await page.goto("/");
  const recording = await page.evaluate(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 320; canvas.height = 240;
    const context = canvas.getContext("2d")!;
    const stream = canvas.captureStream(30);
    const chunks: Blob[] = [];
    const recorder = new MediaRecorder(stream, { mimeType: "video/webm" });
    const done = new Promise<Blob>(resolve => {
      recorder.ondataavailable = e => chunks.push(e.data);
      recorder.onstop = () => resolve(new Blob(chunks, { type: "video/webm" }));
    });
    recorder.start();
    let frame = 0;
    const timer = setInterval(() => { context.fillStyle = `rgb(${100 + frame++ % 20},120,120)`; context.fillRect(0, 0, 320, 240); }, 33);
    setTimeout(() => { recorder.stop(); clearInterval(timer); stream.getTracks().forEach(t => t.stop()); }, 2500);
    return Array.from(new Uint8Array(await (await done).arrayBuffer()));
  });
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-test-recording.webm", mimeType: "video/webm", buffer: Buffer.from(recording),
  });
  await page.getByLabel("I agree to send video frames").check();
  await page.getByRole("button", { name: "Process recording" }).click();
  await expect(page.getByText("Measurement complete", { exact: true })).toBeVisible({ timeout: 80000 });
  await expect(page.getByText("Insufficient usable signal", { exact: true })).toBeVisible();
  await expect(page.getByText("Video recording", { exact: false }).first()).toBeVisible();
});

test("camera consent is required and cancelled setup leaves no measurement", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Start measurement", exact: true }).click();
  const start = page.getByRole("button", { name: "Enable camera & start" });
  await expect(start).toBeDisabled();
  await page.getByLabel("I agree to send video frames").check();
  await expect(start).toBeEnabled();
  await page.getByRole("button", { name: "Close setup" }).click();
  await expect(page.getByText("Camera off", { exact: true })).toBeVisible();
  await expect(page.getByText("Not measuring", { exact: true })).toBeVisible();
});

test("mobile has no horizontal overflow and navigation works", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  await page.getByRole("button", { name: "How it works", exact: true }).click();
  await expect(page.getByRole("heading", { name: "A pulse, seen in a new light." })).toBeVisible();
  await page.getByRole("button", { name: "Session reports", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your first report starts with a moment." })).toBeVisible();
});

test("unavailable backend reports an actionable error without fabricated BPM", async ({ page }) => {
  await page.routeWebSocket("**/ws/measure", socket => socket.close({ code: 1011, reason: "Test outage" }));
  await page.goto("/");
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await page.getByRole("button", { name: "Start simulated session" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Let’s get you connected." })).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again", exact: true })).toBeVisible();
  await expect(page.getByText("Not measuring", { exact: true })).toBeVisible();
});

test("real FacePhys accepts browser frames from a synthetic test camera and stops tracks", async ({ browser }) => {
  const context = await browser.newContext({ permissions: ["camera"] });
  const page = await context.newPage();
  // A canvas stream tests the real browser PNG/socket/model path; it is not a human measurement.
  await page.addInitScript(() => {
    let stream: MediaStream;
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => {
      const canvas = document.createElement("canvas");
      canvas.width = 320; canvas.height = 240;
      const ctx = canvas.getContext("2d")!;
      let i = 0;
      setInterval(() => { ctx.fillStyle = `rgb(${100 + i++ % 20},120,120)`; ctx.fillRect(0, 0, 320, 240); }, 33);
      stream = canvas.captureStream(30);
      (window as unknown as { testStream: MediaStream }).testStream = stream;
      return stream;
    } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start measurement", exact: true }).click();
  await page.getByLabel("I agree to send video frames").check();
  await page.getByRole("button", { name: "Enable camera & start" }).click();
  await expect(page.getByRole("button", { name: "Finish", exact: true })).toBeVisible({ timeout: 80000 });
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", /[2-9]|1[0-9]/, { timeout: 20000 });
  await expect(page.getByText("Find your face", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Finish", exact: true }).click();
  await expect(page.getByText("Insufficient usable signal", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { testStream: MediaStream }).testStream.getTracks().every(t => t.readyState === "ended"))).toBe(true);
  await context.close();
});
