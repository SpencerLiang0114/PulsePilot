export type Mode = "camera" | "recording" | "simulation";
export type CoachingMode = "passive" | "rules" | "meta";
export type AgentMode = "off" | "observe" | "assist" | "adaptive";
export type CoachingState = "MONITORING" | "DECIDING" | "ACTING" | "OBSERVING" | "COOLDOWN";
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
  report_bpm?: number | null;
  display_bpm?: number | null; display_state?: string | null;
  fps: number; latency_ms: number; camera: CameraMetrics; waveform: number[]; waveform_times?: number[];
  processing_ms?: number | null; inference_lag_ms?: number | null;
};
export type Intervention = {
  id: string; issue: string; action: string; started_at: number; evaluated_at: number | null;
  before_sqi: number | null; after_sqi: number | null; delta: number | null;
  before_usable: number | null; after_usable: number | null;
  outcome: "observing" | "improved" | "unchanged" | "worsened" | "inconclusive";
  source: "rules" | "muse"; explanation: string | null;
  action_id: string; decision_source: "rules" | "muse"; explanation_source: "rules" | "muse";
  decision_status: string; before_camera: Record<string, number>; after_camera: Record<string, number>;
  environmental_changes: Record<string, number>;
  agent_event_id?: string | null; graph_version?: string | null;
  model_latency_ms?: number | null; graph_latency_ms?: number | null;
};
export type Statement = { kind: "fact" | "possible explanation" | "limitation"; text: string; evidence_ids: string[] };
export type Analysis = { summary: Statement[]; quality: Statement[]; interventions: Statement[]; recommendations: Statement[] };
export type GroundedClaim = {
  claim_id: string; claim_type: string; section: keyof Analysis; kind: "measurement" | "quality" | "outcome" | "limitation";
  statement_kind: Statement["kind"]; evidence_id: string; metric: string; value: number | string | null; text: string;
};
export type CaptureDiagnostics = {
  initialization_ms: number; width: number; height: number; track_fps: number | null;
  frame_callbacks: number; frames_sent: number; frames_acknowledged: number;
  callback_fps: number | null; sent_fps: number | null;
  mean_ack_round_trip_ms: number | null; max_ack_round_trip_ms: number | null;
  sample_age_observations: number; mean_sample_frame_age_ms: number | null; max_sample_frame_age_ms: number | null;
  max_sample_gap_ms: number | null;
};
export type HealthContext = { activity: "resting" | "active" | "recovery" | "unknown"; concerning_symptoms: boolean };
export type HealthInsight = {
  insight_id: string; category: "measurement" | "education" | "wellness" | "follow_up" | "limitation";
  title: string; text: string; priority: number; evidence_ids: string[]; guidance_reference_ids: string[];
};
export type HealthInsightBundle = {
  report_id: string; status: "pending" | "complete" | "fallback" | "unavailable" | "not_requested";
  analyst: "deterministic" | "muse"; insights: HealthInsight[]; limitations: HealthInsight[];
  evidence: Record<string, string>; guidance_references: Record<string, { title: string; url: string | null }>;
  sufficient_evidence: boolean; graph_version: string; agent_event_id: string | null;
};
export type PulseVariability = {
  status: "available" | "insufficient" | "simulation"; method: string; reason: string;
  rmssd_ms: number | null; sdnn_ms: number | null; duration: number; interval_count: number;
  rejected_intervals: number; interval_times: number[]; intervals_ms: number[];
};
export type Report = {
  id: string; created_at: string; mode: Mode; analyst: "deterministic" | "muse"; ai_status: string;
  stats: {
    mean_bpm: number | null; median_bpm: number | null; min_bpm: number | null; max_bpm: number | null;
    sd_bpm: number | null; mean_sqi: number | null; usable_fraction: number; tracking_fraction: number;
    signal_coverage: number; duration: number; stable_at: number | null; mean_fps: number;
    mean_latency_ms: number; lighting_issue_fraction: number; motion_issue_fraction: number; alignment_issue_fraction: number;
  };
  samples: Sample[]; interventions: Intervention[]; evidence: Record<string, string>; analysis: Analysis; claims: GroundedClaim[];
  agent_event_id?: string | null; graph_version?: string | null;
  agent_mode?: AgentMode | null;
  agent_telemetry?: { event_id: string; session_id: string; event_type: "coach_request" | "report_request" | "health_insight_request";
    graph_version: string; model_identifier: string | null; route: string; status: string;
    validation_result: boolean; fallback_reason: string | null; model_latency_ms: number; graph_latency_ms: number;
    api_requests: number; input_tokens: number | null; output_tokens: number | null }[];
  capture_diagnostics?: CaptureDiagnostics | null;
  health_context?: HealthContext;
  health_insights?: HealthInsightBundle | null;
  pulse_variability?: PulseVariability;
};
export type Health = { status: string; weights_available: boolean; model_ready: boolean; model_error: string | null; busy: boolean; ai_configured: boolean; agent_mode?: AgentMode };

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
export const decisionLabel = (item: Intervention) => item.decision_source === "muse" ? "Muse Spark decision"
  : item.explanation_source === "muse" ? "Rules decision · Muse Spark explanation"
  : item.decision_status.startsWith("explanation_fallback_") ? "Rules decision · Muse explanation unavailable"
  : item.decision_status.startsWith("fallback_") ? `Rules fallback · ${item.decision_status.slice(9).replaceAll("_", " ")}`
  : item.decision_status === "safety" ? "Deterministic safety instruction" : "Rules decision";
