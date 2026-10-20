"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { backendUrl, Health, Intervention, Mode, Report, Sample } from "./types";

type StartOptions = { mode: Mode; duration: number; aiConsent: boolean; frameConsent: boolean; file?: File };

export function useMeasurement(onReport: (report: Report) => void) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const objectUrl = useRef<string | null>(null);
  const generation = useRef(0);
  const onReportRef = useRef(onReport);
  const pendingReport = useRef<Report | null>(null);
  const statusRef = useRef("idle");
  const [status, setStatus] = useState<"idle" | "connecting" | "measuring" | "finishing" | "complete" | "error">("idle");
  const [mode, setMode] = useState<Mode>("camera");
  const [duration, setDuration] = useState(60);
  const [sample, setSample] = useState<Sample | null>(null);
  const [history, setHistory] = useState<Sample[]>([]);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [aiStatus, setAiStatus] = useState("not_configured");
  const [captureSize, setCaptureSize] = useState({ width: 640, height: 480 });
  onReportRef.current = onReport;
  statusRef.current = status;

  const releaseCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
    const video = videoRef.current;
    if (video) { video.pause(); video.srcObject = null; video.removeAttribute("src"); video.load(); }
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
  }, []);

  const cancel = useCallback(() => {
    if (pendingReport.current) {
      onReportRef.current({ ...pendingReport.current, ai_status: "cancelled" });
      pendingReport.current = null;
    }
    generation.current += 1;
    socketRef.current?.close();
    socketRef.current = null;
    releaseCamera();
    setSample(null);
    setStatus("idle");
    setError(null);
  }, [releaseCamera]);

  const refreshHealth = useCallback(async () => {
    try {
      const response = await fetch(`${backendUrl()}/health`, { signal: AbortSignal.timeout(4000) });
      if (!response.ok) throw new Error("Unavailable");
      setHealth(await response.json());
    } catch { setHealth(null); }
  }, []);

  useEffect(() => {
    void refreshHealth();
    return () => { generation.current++; socketRef.current?.close(); releaseCamera(); };
  }, [refreshHealth, releaseCamera]);

  const finish = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: "finish" }));
      setStatus("finishing");
      statusRef.current = "finishing";
      releaseCamera();
      setSample(current => current ? { ...current, bpm: null, usable: false } : null);
    }
  }, [releaseCamera]);

  const extend = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN)
      socketRef.current.send(JSON.stringify({ type: "extend" }));
  }, []);

  const start = useCallback(async (options: StartOptions) => {
    cancel();
    const run = ++generation.current;
    setStatus("connecting");
    statusRef.current = "connecting";
    setMode(options.mode);
    setDuration(options.duration);
    setHistory([]);
    setInterventions([]);
    setMessage("Connecting to the measurement service…");
    let receivedReport = false;
    let inFlight = 0;
    let previousFrame = -1;
    let lastAck = performance.now();
    let socket: WebSocket;
    const fail = (text: string) => {
      if (generation.current !== run) return;
      generation.current++;
      setError(text);
      setStatus("error");
      statusRef.current = "error";
      setSample(null);
      releaseCamera();
      socket?.close();
    };
    try {
      const url = new URL(backendUrl());
      if (window.location.protocol === "https:" && url.protocol !== "https:") {
        throw new Error("This secure website needs an HTTPS inference service. Configure the backend URL and retry.");
      }
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      url.pathname = "/ws/measure";
      socket = new WebSocket(url);
      socketRef.current = socket;
    } catch (err) { fail(err instanceof Error ? err.message : "Could not connect."); return; }
    const connectionTimeout = window.setTimeout(() => {
      if (generation.current === run && statusRef.current === "connecting")
        fail("The measurement service took too long to initialize. Check the backend and try again.");
    }, 90000);
    socket.onopen = () => socket.send(JSON.stringify({
      type: "start", mode: options.mode, duration: options.duration,
      ai_consent: options.aiConsent, frame_consent: options.frameConsent, coaching: "meta",
    }));
    socket.onerror = () => fail("The measurement service is unavailable. Start the Python backend or check its connection, then retry.");
    socket.onclose = () => {
      window.clearTimeout(connectionTimeout);
      if (generation.current !== run) return;
      releaseCamera();
      if (pendingReport.current) {
        onReportRef.current({ ...pendingReport.current, ai_status: "unavailable" });
        pendingReport.current = null;
      }
      if (!receivedReport) fail("The connection ended before the report was ready. Please restart the measurement.");
    };
    const beginCapture = async () => {
      if (options.mode === "simulation") return;
      const video = videoRef.current;
      if (!video) throw new Error("The camera preview could not initialize.");
      if (options.mode === "recording") {
        if (!options.file) throw new Error("Choose a video recording first.");
        objectUrl.current = URL.createObjectURL(options.file);
        video.src = objectUrl.current;
        video.loop = false;
        video.onended = finish;
      } else {
        if (!navigator.mediaDevices?.getUserMedia)
          throw new Error("Camera access requires HTTPS or localhost in a supported browser.");
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30, max: 30 }, facingMode: "user" },
          audio: false,
        });
        if (generation.current !== run) { stream.getTracks().forEach(track => track.stop()); return; }
        streamRef.current = stream;
        video.srcObject = stream;
        stream.getVideoTracks()[0].onended = () => fail("The camera was disconnected. Reconnect it and start again.");
      }
      await video.play();
      if (generation.current !== run) return;
      setCaptureSize({ width: video.videoWidth, height: video.videoHeight });
      const canvas = document.createElement("canvas");
      const ratio = Math.min(320 / video.videoWidth, 240 / video.videoHeight, 1);
      canvas.width = Math.max(32, Math.round(video.videoWidth * ratio));
      canvas.height = Math.max(32, Math.round(video.videoHeight * ratio));
      const context = canvas.getContext("2d", { alpha: false });
      if (!context) throw new Error("The browser could not initialize camera capture.");
      const capture = async (_now: number, metadata?: VideoFrameCallbackMetadata) => {
        if (generation.current !== run || statusRef.current !== "measuring") return;
        if (performance.now() - lastAck > 5000) {
          fail("Frames stopped reaching the inference service. Check your connection and restart.");
          return;
        }
        const timestamp = metadata?.mediaTime ?? video.currentTime;
        if (inFlight < 4 && socket.bufferedAmount < 1_500_000 && timestamp > previousFrame && socket.readyState === WebSocket.OPEN) {
          previousFrame = timestamp;
          inFlight += 1;
          context.drawImage(video, 0, 0, canvas.width, canvas.height);
          const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, "image/png"));
          if (generation.current !== run || statusRef.current !== "measuring") return;
          if (!blob) { fail("Could not encode a camera frame."); return; }
          const image = await blob.arrayBuffer();
          if (generation.current !== run || statusRef.current !== "measuring") return;
          const packet = new Uint8Array(8 + image.byteLength);
          new DataView(packet.buffer).setFloat64(0, timestamp, true);
          packet.set(new Uint8Array(image), 8);
          if (socket.readyState === WebSocket.OPEN) socket.send(packet);
        }
        if ("requestVideoFrameCallback" in video) video.requestVideoFrameCallback(capture);
        else requestAnimationFrame(capture);
      };
      lastAck = performance.now();
      if ("requestVideoFrameCallback" in video) video.requestVideoFrameCallback(capture);
      else requestAnimationFrame(capture);
    };
    socket.onmessage = async event => {
      if (generation.current !== run) return;
      try {
        const payload = JSON.parse(event.data);
        switch (payload.type) {
          case "status": setMessage(payload.message); break;
          case "ready":
            window.clearTimeout(connectionTimeout);
            setAiStatus(payload.ai_status);
            setStatus("measuring");
            statusRef.current = "measuring";
            await beginCapture();
            break;
          case "ack": inFlight = Math.max(0, inFlight - 1); lastAck = performance.now(); break;
          case "sample":
            setSample(payload.sample);
            setHistory(current => [...current, payload.sample]);
            setInterventions(payload.interventions);
            break;
          case "coach": setInterventions(payload.interventions); break;
          case "duration": setDuration(payload.duration); break;
          case "report":
            receivedReport = true;
            pendingReport.current = payload.report.ai_status === "pending" ? payload.report : null;
            releaseCamera();
            setStatus("complete");
            statusRef.current = "complete";
            onReportRef.current(payload.report);
            break;
          case "error": fail(payload.message); break;
        }
      } catch (err) {
        const denied = err instanceof DOMException && err.name === "NotAllowedError";
        fail(denied ? "Camera permission was denied. Allow camera access in your browser’s site settings, then try again."
          : err instanceof Error ? err.message : "The measurement could not start.");
      }
    };
  }, [cancel, finish, releaseCamera]);

  return { videoRef, status, mode, duration, sample, history, interventions, error, message, health,
    aiStatus, captureSize, start, finish, extend, cancel, refreshHealth };
}
