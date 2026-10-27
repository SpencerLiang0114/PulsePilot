import { expect, test, type Page } from "@playwright/test";
import type { Sample } from "../lib/types";

const accepted: Sample = {
  t: 0, bpm: 72, sqi: 0.9, usable: true, state: "Signal stable", fps: 30, latency_ms: 10,
  waveform: [0, 1, 0, -1], waveform_times: [0, 1/30, 2/30, 3/30],
  camera: {
    face_visible: true, face_count: 1, confidence: 1, center_offset: 0, face_size: 0.4,
    yaw_proxy: 0, roll_degrees: 0, brightness: 120, light_imbalance: 0, light_change: 0,
    motion: 0, visibility_proxy: 1, bbox: null, landmarks: [],
  },
};

type CameraWindow = Window & { freezeCapture: () => void; testStream: MediaStream; cameraConstraints: MediaStreamConstraints };

async function camera(page: Page) {
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", { value: async (constraints: MediaStreamConstraints) => {
      (window as unknown as CameraWindow).cameraConstraints = constraints;
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
  let sendHeatmap = true;
  let freezeHeatmap = false;
  let heatmapPulse = 0;
  let heatmapTimestamp = 0;
  await page.routeWebSocket("**/ws/measure", socket => {
    let t = 0;
    socket.onMessage(message => {
      if (typeof message === "string") {
        if (JSON.parse(message).type === "start") socket.send(JSON.stringify({ type: "ready", ai_status: "not_requested" }));
        return;
      }
      t += 1/30;
      socket.send(JSON.stringify({ type: "ack" }));
      if (!freezeHeatmap) heatmapTimestamp = t;
      if (sendHeatmap) socket.send(JSON.stringify({ type: "face_heatmap", heatmap: faceVisible ? {
        t: heatmapTimestamp, pulse: heatmapPulse, bbox: [.2, .2, .65, .7], width: 36, height: 36,
        values: Array.from({ length: 1296 }, (_, i) => Math.round(i / 1295 * 255)),
      } : null }));
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
  const heatmap = page.getByRole("img", { name: "FacePhys attention heatmap" });
  const toggle = page.getByRole("switch", { name: "Face heatmap" });
  await expect(heatmap).toBeVisible();
  const checkAlignment = async () => {
    const error = await heatmap.locator("canvas").evaluate((canvas: HTMLCanvasElement) => {
      const video = document.querySelector("video")!;
      const stage = video.getBoundingClientRect();
      const scale = Math.min(stage.width / video.videoWidth, stage.height / video.videoHeight);
      const contentWidth = video.videoWidth * scale, contentHeight = video.videoHeight * scale;
      const map = canvas.getBoundingClientRect();
      return Math.max(
        Math.abs(map.x - (stage.x + (stage.width - contentWidth) / 2 + .35 * contentWidth)),
        Math.abs(map.y - (stage.y + (stage.height - contentHeight) / 2 + .2 * contentHeight)),
        Math.abs(map.width - .45 * contentWidth), Math.abs(map.height - .5 * contentHeight),
      );
    });
    expect(error).toBeLessThan(1);
  };
  await checkAlignment();
  await expect(heatmap).toHaveClass(/mirrored/);
  await expect(page.getByRole("img", { name: "Detected face", exact: true }).locator("rect")).toHaveAttribute("x", "64");
  await expect.poll(() => heatmap.locator("canvas").evaluate((canvas: HTMLCanvasElement) =>
    canvas.getContext("2d")!.getImageData(18, 18, 1, 1).data[3])).toBeGreaterThan(0);
  await expect(heatmap).toHaveCSS("mix-blend-mode", "normal");
  const pixel = (x: number, y: number) => heatmap.locator("canvas").evaluate((canvas: HTMLCanvasElement, [px, py]) =>
    Array.from(canvas.getContext("2d")!.getImageData(px, py, 1, 1).data), [x, y]);
  expect(await pixel(0, 0)).toEqual([0, 0, 0, 0]);
  expect(await pixel(35, 35)).toEqual([255, 230, 30, 255]);
  const midrange = await pixel(18, 18);
  expect(midrange[0]).toBe(255);
  expect(midrange[1]).toBeLessThan(125);
  expect(midrange[3]).toBeGreaterThan(180);
  heatmapPulse = 1;
  await expect.poll(async () => (await pixel(35, 35))[1]).toBe(255);
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect(heatmap).toHaveCount(0);
  await toggle.click();
  await expect(heatmap).toBeVisible();
  await expect(page.locator(".camera-reading strong")).toHaveText("72.0");
  await expect(page.getByRole("img", { name: "Pulse waveform below camera preview" })).toBeVisible();
  const previewBounds = await video.boundingBox();
  const waveformBounds = await page.locator(".camera-signal").boundingBox();
  expect(waveformBounds!.y).toBeGreaterThanOrEqual(previewBounds!.y + previewBounds!.height);
  await page.screenshot({ path: "test-results/live-camera-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await checkAlignment();
  await page.screenshot({ path: "test-results/live-camera-mobile.png", fullPage: true });
  sendHeatmap = false;
  await expect(heatmap).toHaveCount(0, { timeout: 2000 });
  sendHeatmap = true;
  await expect(heatmap).toBeVisible();
  freezeHeatmap = true;
  await expect(heatmap).toHaveCount(0, { timeout: 2000 });
  freezeHeatmap = false;
  await expect(heatmap).toBeVisible();
  faceVisible = false;
  await expect(page.getByRole("img", { name: "Detected face", exact: true })).toHaveCount(0);
  await expect(heatmap).toHaveCount(0);
  await expect(page.locator(".camera-reading strong")).toHaveText("—");
  await expect(video).toHaveCSS("opacity", "1");
  await page.getByRole("button", { name: "Finish", exact: true }).click();
  await expect(toggle).toHaveCount(0);
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

test("heatmap bridges brief tracking misses while heart rate still follows current quality", async ({ page }) => {
  await camera(page);
  let tracking: "visible" | "held" | "lost" | "multiple" = "visible";
  let heldFrames = 0;
  let sendAttention = true;
  await page.routeWebSocket("**/ws/measure", socket => {
    let t = 0, modelTime = 0;
    socket.onMessage(message => {
      if (typeof message === "string") {
        if (JSON.parse(message).type === "start") socket.send(JSON.stringify({ type: "ready", ai_status: "not_requested" }));
        return;
      }
      t += 1/30;
      socket.send(JSON.stringify({ type: "ack" }));
      const visible = tracking === "visible";
      if (visible) modelTime = t;
      if (tracking === "held") heldFrames++;
      const metrics = { ...accepted.camera, face_visible: visible, face_count: visible ? 1 : tracking === "multiple" ? 2 : 0,
        confidence: .6, face_size: .18, bbox: visible ? [.4, .3, .6, .55] : null };
      if (sendAttention) socket.send(JSON.stringify({ type: "face_heatmap", t, camera: metrics,
        heatmap: visible || tracking === "held" ? {
          t: modelTime, bbox: [.4, .3, .6, .55], width: 36, height: 36, values: Array(1296).fill(128),
        } : null,
      }));
      socket.send(JSON.stringify({ type: "sample", interventions: [], sample: {
        ...accepted, t, bpm: visible ? 72 : null, usable: visible, camera: metrics,
      } }));
    });
  });
  await page.goto("/");
  await start(page);
  const heatmap = page.getByRole("img", { name: "FacePhys attention heatmap" });
  await expect(heatmap).toBeVisible();
  sendAttention = false;
  // This deliberate one-second gap must bridge the old 750 ms display timeout.
  await page.waitForTimeout(1000);
  await expect(heatmap).toBeVisible();
  sendAttention = true;
  tracking = "held";
  await expect(page.locator("#heatmap-description")).toHaveText("Reacquiring face…");
  await expect.poll(() => heldFrames).toBeGreaterThanOrEqual(25);
  await expect(heatmap).toBeVisible();
  await expect(page.locator(".heart-value")).toHaveText("—BPM");
  tracking = "visible";
  await expect(page.locator("#heatmap-description")).toHaveText("FacePhys attention");
  await expect(heatmap).toBeVisible();
  tracking = "multiple";
  await expect(heatmap).toHaveCount(0);
  tracking = "visible";
  await expect(heatmap).toBeVisible();
  tracking = "lost";
  await expect(heatmap).toHaveCount(0);
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


test("tracking and heatmap position update between measurement and model samples", async ({ page }) => {
  await camera(page);
  let advance = false;
  await page.routeWebSocket("**/ws/measure", socket => {
    let t = 0;
    socket.onMessage(message => {
      if (typeof message === "string") {
        if (JSON.parse(message).type === "start") socket.send(JSON.stringify({ type: "ready", ai_status: "not_requested" }));
        return;
      }
      t += 1/60;
      socket.send(JSON.stringify({ type: "ack" }));
      if (t === 1/60) socket.send(JSON.stringify({ type: "sample", interventions: [], sample: { ...accepted, t } }));
      const bbox = advance ? [.4, .2, .8, .7] : [.2, .2, .6, .7];
      socket.send(JSON.stringify({ type: "face_heatmap", t,
        camera: { ...accepted.camera, bbox },
        heatmap: { t: 0, bbox, width: 36, height: 36, values: Array(1296).fill(128) },
      }));
    });
  });
  await page.goto("/");
  await start(page);
  expect(await page.evaluate(() => (window as unknown as CameraWindow).cameraConstraints.video)).toMatchObject({ frameRate: { ideal: 60, max: 60 } });
  const rect = page.getByRole("img", { name: "Detected face", exact: true }).locator("rect");
  const map = page.getByRole("img", { name: "FacePhys attention heatmap" }).locator("foreignObject");
  await expect(rect).toHaveAttribute("x", "64");
  advance = true;
  await expect(rect).toHaveAttribute("x", "128");
  await expect(map).toHaveAttribute("x", "128");
  await expect(page.locator(".heart-value")).toHaveText("72BPM");
});

test("waveform uses signal times, scrolls between updates, and shows readable scales", async ({ page }) => {
  await camera(page);
  let nextTime = 12;
  let sentTime = -1;
  await page.routeWebSocket("**/ws/measure", socket => {
    socket.onMessage(message => {
      if (typeof message === "string") {
        if (JSON.parse(message).type === "start") socket.send(JSON.stringify({ type: "ready", ai_status: "not_requested" }));
        return;
      }
      socket.send(JSON.stringify({ type: "ack" }));
      if (sentTime === nextTime) return;
      sentTime = nextTime;
      socket.send(JSON.stringify({ type: "sample", interventions: [], sample: {
        ...accepted, t: nextTime,
        waveform: Array.from({ length: 240 }, (_, i) => Math.sin(i / 30 * 2 * Math.PI * 1.2)),
        waveform_times: Array.from({ length: 240 }, (_, i) => nextTime - 8 + i / 30),
      } }));
    });
  });
  await page.goto("/");
  await start(page);
  const chart = page.locator(".camera-signal .pulse-waveform");
  const trace = chart.locator(".wave-trace");
  await expect(chart).toContainText("BVP · normalized");
  await expect(chart).toContainText("2.0");
  await expect(chart).toContainText("12s");
  const initial = await trace.getAttribute("d");
  await expect.poll(() => trace.getAttribute("d")).not.toBe(initial);
  const pointCount = (initial?.match(/[ML]/g) ?? []).length;
  expect(pointCount).toBe(240);
  const box = await chart.boundingBox();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + 50);
  await expect(chart.locator(".chart-tooltip")).toContainText("normalized BVP");
  nextTime = 15;
  await expect.poll(async () => Number(await chart.getAttribute("data-window-start"))).toBeGreaterThanOrEqual(7);
  await expect(chart).toContainText("15s");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const readingBox = await page.locator(".camera-reading").boundingBox();
  const signalBox = await page.locator(".camera-signal").boundingBox();
  expect(signalBox!.y).toBeGreaterThan(readingBox!.y + readingBox!.height);
  await page.screenshot({ path: "test-results/scrolling-waveform-mobile.png", fullPage: true });
});
