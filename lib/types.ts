export type Mode = "camera" | "recording" | "simulation";
export type FaceHeatmap = {
  t: number; bbox: number[]; width: number; height: number; values: number[]; pulse?: number;
};
export type CameraMetrics = {
  face_visible: boolean; face_count: number; confidence: number; center_offset: number;
  face_size: number; yaw_proxy: number; roll_degrees: number; brightness: number;
  light_imbalance: number; light_change: number; motion: number; visibility_proxy: number;
  bbox: number[] | null; landmarks: number[][];
};
export type Sample = {
  t: number; bpm: number | null; sqi: number | null; usable: boolean; state: string;
  fps: number; latency_ms: number; camera: CameraMetrics; waveform: number[]; waveform_times?: number[];
};
export type Intervention = {
  id: string; issue: string; action: string; started_at: number; evaluated_at: number | null;
  before_sqi: number | null; after_sqi: number | null; delta: number | null;
  before_usable: number | null; after_usable: number | null;
  outcome: "observing" | "improved" | "unchanged" | "worsened" | "inconclusive";
  source: "rules" | "muse"; explanation: string | null;
};
export type Statement = { kind: "fact" | "possible explanation" | "limitation"; text: string; evidence_ids: string[] };
export type Analysis = { summary: Statement[]; quality: Statement[]; interventions: Statement[]; recommendations: Statement[] };
export type Report = {
  id: string; created_at: string; mode: Mode; analyst: "deterministic" | "muse"; ai_status: string;
  stats: {
    mean_bpm: number | null; median_bpm: number | null; min_bpm: number | null; max_bpm: number | null;
    sd_bpm: number | null; mean_sqi: number | null; usable_fraction: number; tracking_fraction: number;
    signal_coverage: number; duration: number; stable_at: number | null; mean_fps: number;
    mean_latency_ms: number; lighting_issue_fraction: number; motion_issue_fraction: number; alignment_issue_fraction: number;
  };
  samples: Sample[]; interventions: Intervention[]; evidence: Record<string, string>; analysis: Analysis;
};
export type Health = { status: string; weights_available: boolean; model_ready: boolean; model_error: string | null; busy: boolean; ai_configured: boolean };

export function backendUrl() {
  const configured = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window === "undefined") return "http://localhost:8000";
  return ["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : window.location.origin;
}
export const percent = (n: number | null | undefined) => n == null ? "—" : `${Math.round(n * 100)}%`;
export const clockText = (n: number) => `${Math.floor(n / 60)}:${Math.floor(n % 60).toString().padStart(2, "0")}`;
