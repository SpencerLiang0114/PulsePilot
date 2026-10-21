import { expect, test, type Page } from "@playwright/test";
import type { Sample } from "../lib/types";

const accepted: Sample = {
  t: 0, bpm: 72, sqi: 0.9, usable: true, state: "Signal stable", fps: 30, latency_ms: 10,
  waveform: [0, 1, 0, -1],
  camera: {
    face_visible: true, face_count: 1, confidence: 1, center_offset: 0, face_size: 0.4,
    yaw_proxy: 0, roll_degrees: 0, brightness: 120, light_imbalance: 0, light_change: 0,
    motion: 0, visibility_proxy: 1, bbox: null, landmarks: [],
  },
};

type CameraWindow = Window & { freezeCapture: () => void; testStream: MediaStream };

async function camera(page: Page) {
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => {
      const canvas = document.createElement("canvas");
      canvas.width = 320; canvas.height = 240;
      const context = canvas.getContext("2d")!;
      const stream = canvas.captureStream(30);
      let frame = 0;
      const timer = setInterval(() => {
        context.fillStyle = `rgb(${100 + frame++ % 20},120,120)`;
        context.fillRect(0, 0, 320, 240);
        if (stream.getTracks().every(track => track.readyState === "ended")) clearInterval(timer);
      }, 33);
      (window as unknown as CameraWindow).freezeCapture = () => clearInterval(timer);
      (window as unknown as CameraWindow).testStream = stream;
      return stream;
    } });
  });
  await page.route("**/health", route => route.fulfill({ json: { status: "ok", ai_configured: false } }));
}

async function start(page: Page) {
  await page.getByRole("button", { name: "Start measurement", exact: true }).click();
  await page.getByLabel("I agree to send video frames").check();
  await page.getByRole("button", { name: "Enable camera & start" }).click();
  await expect(page.locator(".heart-value")).toHaveText("72BPM");
  await expect(page.locator(".measurement-state")).toHaveText("Signal stable");
}

test("live preview shows face tracking and signal, clears lost faces, and stops the camera", async ({ page }) => {
  await camera(page);
  let faceVisible = true;
  await page.routeWebSocket("**/ws/measure", socket => {
    let t = 0;
    socket.onMessage(message => {
      if (typeof message === "string") {
        if (JSON.parse(message).type === "start") socket.send(JSON.stringify({ type: "ready", ai_status: "not_requested" }));
        return;
      }
      t += 1/30;
      socket.send(JSON.stringify({ type: "ack" }));
      socket.send(JSON.stringify({ type: "sample", interventions: [], sample: {
        ...accepted, t, bpm: faceVisible ? 72 : null, usable: faceVisible,
        state: faceVisible ? "Signal stable" : "Find your face",
        camera: { ...accepted.camera, face_visible: faceVisible, bbox: faceVisible ? [.3, .2, .7, .7] : null },
      } }));
    });
  });
  await page.goto("/");
  await start(page);
  const video = page.getByLabel("Live camera or recording preview");
  await expect(video).toHaveCSS("opacity", "1");
  await expect.poll(() => video.evaluate((el: HTMLVideoElement) => !el.paused && el.videoWidth > 0)).toBe(true);
  await expect(page.getByRole("img", { name: "Detected face", exact: true })).toBeVisible();
  await expect(page.locator(".camera-reading strong")).toHaveText("72.0");
  await expect(page.getByRole("img", { name: "Pulse waveform over camera preview" })).toBeVisible();
  await page.screenshot({ path: "test-results/live-camera-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/live-camera-mobile.png", fullPage: true });
  faceVisible = false;
  await expect(page.getByRole("img", { name: "Detected face", exact: true })).toHaveCount(0);
  await expect(page.locator(".camera-reading strong")).toHaveText("—");
  await expect(video).toHaveCSS("opacity", "1");
  await page.getByRole("button", { name: "Finish", exact: true }).click();
  expect(await page.evaluate(() => (window as unknown as CameraWindow).testStream.getTracks().every(track => track.readyState === "ended"))).toBe(true);
});

test("denied camera permission offers recovery without showing a live preview", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async () => {
      throw new DOMException("Permission denied", "NotAllowedError");
    } });
  });
  await page.routeWebSocket("**/ws/measure", socket => {
    socket.onMessage(() => socket.send(JSON.stringify({ type: "ready", ai_status: "not_requested" })));
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start measurement", exact: true }).click();
  await page.getByLabel("I agree to send video frames").check();
  await page.getByRole("button", { name: "Enable camera & start" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Let’s get you connected." })).toContainText("Camera permission was denied");
  await expect(page.getByLabel("Live camera or recording preview")).toHaveCSS("opacity", "0");
  await expect(page.locator(".camera-reading")).toHaveCount(0);
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
});

for (const stalled of ["capture", "samples", "sample timestamps", "acknowledgements"] as const) {
  test(`invalidates stale ${stalled} while the socket stays open, then restarts`, async ({ page }) => {
    await camera(page);
    let stalledNow = false;
    let closed = false;
    let frames = 0;
    const timers: ReturnType<typeof setInterval>[] = [];
    await page.routeWebSocket("**/ws/measure", socket => {
      let t = 0;
      socket.onMessage(message => {
        if (typeof message !== "string") { frames++; return; }
        if (JSON.parse(message).type !== "start") return;
        socket.send(JSON.stringify({ type: "ready", ai_status: "not_requested" }));
        const timer = setInterval(() => {
          if (!stalledNow || stalled !== "acknowledgements") socket.send(JSON.stringify({ type: "ack" }));
          if (stalledNow && stalled === "samples") return;
          if (!stalledNow || stalled !== "sample timestamps") t += 0.1;
          socket.send(JSON.stringify({ type: "sample", sample: { ...accepted, t }, interventions: [] }));
        }, 100);
        timers.push(timer);
        socket.onClose(() => { closed = true; clearInterval(timer); });
      });
    });
    try {
      await page.goto("/");
      await start(page);
      await expect.poll(() => frames).toBeGreaterThan(5);
      stalledNow = true;
      if (stalled === "capture") await page.evaluate(() => (window as unknown as CameraWindow).freezeCapture());
      expect(closed).toBe(false);
      // Five seconds of freshness plus one 250 ms watchdog tick and assertion scheduling.
      await expect(page.locator(".heart-value")).toHaveText("—BPM", { timeout: 5500 });
      await expect(page.locator(".measurement-state")).toHaveText("Not measuring");
      await expect(page.getByRole("alert").filter({ hasText: "Let’s get you connected." })).toContainText(/stopped|stale/i);
      await expect(page.getByRole("button", { name: "Try again", exact: true })).toBeVisible();
      expect(await page.evaluate(() => (window as unknown as CameraWindow).testStream.getTracks().every(t => t.readyState === "ended"))).toBe(true);
      await expect.poll(() => closed).toBe(true);

      stalledNow = false;
      await start(page);
      // Keep healthy capture/ACKs/samples running past the previous session's deadline.
      await page.waitForTimeout(6000);
      await expect(page.locator(".heart-value")).toHaveText("72BPM");
      await expect(page.getByRole("alert").filter({ hasText: "Let’s get you connected." })).toHaveCount(0);
      await page.getByRole("button", { name: "Finish", exact: true }).click();
      // A slow report must not trigger a measurement freshness error after finish.
      await page.waitForTimeout(5500);
      await expect(page.getByRole("button", { name: "Preparing report" })).toBeVisible();
      await expect(page.getByRole("alert").filter({ hasText: "Let’s get you connected." })).toHaveCount(0);
      await expect(page.locator(".heart-value")).toHaveText("—BPM");
    } finally {
      timers.forEach(clearInterval);
    }
  });
}
