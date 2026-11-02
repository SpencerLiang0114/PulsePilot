import { expect, test, type Page } from "@playwright/test";
import type { Sample } from "../lib/types";

const sample: Sample = {
  t: 1, bpm: 72, sqi: .9, usable: true, state: "Signal stable", fps: 30, latency_ms: 10,
  waveform: [0, 1, 0, -1], waveform_times: [0, 1/30, 2/30, 3/30],
  camera: {
    face_visible: true, face_count: 1, confidence: 1, center_offset: 0, face_size: .4,
    yaw_proxy: 0, roll_degrees: 0, brightness: 120, light_imbalance: 0, light_change: 0,
    motion: 0, visibility_proxy: 1, bbox: [.3, .2, .7, .8], landmarks: [],
  },
};

async function expectWorkspaceToFit(page: Page) {
  await expect.poll(() => page.evaluate(() => ({
    horizontal: document.documentElement.scrollWidth > innerWidth,
    vertical: document.documentElement.scrollHeight > innerHeight,
  }))).toEqual({ horizontal: false, vertical: false });
  for (const selector of [".capture-stage", ".capture-controls", ".pulse-waveform", ".heart-panel", ".coach-panel", ".conditions-panel", ".measurement-footnote"]) {
    await expect(page.locator(selector)).toBeInViewport({ ratio: 1 });
  }
}

// The screenshots show a Retina display: roughly 1258 × 902 CSS pixels after Chrome's sidebar.
for (const viewport of [{ width: 1258, height: 902 }, { width: 1280, height: 800 }, { width: 1040, height: 720 }, { width: 1440, height: 780 }]) {
  test(`measurement fits at 100% zoom in a ${viewport.width} × ${viewport.height} window`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.route("**/health", route => route.fulfill({ json: { status: "ok", model_ready: true, ai_configured: false } }));
    await page.addInitScript(() => {
      Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => {
        const canvas = document.createElement("canvas");
        canvas.width = 640; canvas.height = 480;
        const context = canvas.getContext("2d")!;
        const stream = canvas.captureStream(30);
        const timer = setInterval(() => {
          context.fillStyle = "#536e66";
          context.fillRect(0, 0, canvas.width, canvas.height);
          if (stream.getTracks().every(track => track.readyState === "ended")) clearInterval(timer);
        }, 33);
        return stream;
      } });
    });
    let stable = true;
    await page.routeWebSocket("**/ws/measure", socket => {
      let t = 1;
      socket.onMessage(message => {
        if (typeof message === "string") {
          if (JSON.parse(message).type === "start") socket.send(JSON.stringify({ type: "ready" }));
        } else {
          socket.send(JSON.stringify({ type: "ack" }));
          socket.send(JSON.stringify({ type: "sample", sample: {
            ...sample, t: t += 1/30, usable: stable, bpm: stable ? 72 : null, state: stable ? "Signal stable" : "Finding signal",
          }, interventions: [] }));
        }
      });
    });
    await page.goto("/");
    await page.evaluate(() => document.fonts.ready);
    await expectWorkspaceToFit(page);
    const idleHeight = await page.locator(".capture-stage").evaluate(element => element.clientHeight);
    await page.getByRole("button", { name: "Start measurement", exact: true }).click();
    await page.getByRole("button", { name: "Enable camera & start" }).click();
    await expect(page.locator(".heart-value")).toHaveText("72BPM");
    await expectWorkspaceToFit(page);
    expect(await page.locator(".capture-stage").evaluate(element => element.clientHeight)).toBe(idleHeight);
    await expect(page.getByRole("button", { name: "Finish", exact: true })).toBeInViewport({ ratio: 1 });
    await expect(page.getByRole("img", { name: "Detected face" })).toBeInViewport({ ratio: 1 });
    await page.screenshot({ path: `test-results/layout-${viewport.width}-${viewport.height}.png` });
    stable = false;
    await expect(page.locator(".heart-value")).toHaveText("—BPM");
    await expectWorkspaceToFit(page);
    await page.getByRole("button", { name: "Expand camera preview" }).click();
    await expect.poll(() => page.locator(".capture-stage").evaluate(element => element.clientHeight)).toBe(viewport.height);
    await page.getByRole("button", { name: "Expand camera preview" }).click();
    await expectWorkspaceToFit(page);
  });
}
