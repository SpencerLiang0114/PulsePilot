"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import {
  Activity, ArrowRight, Camera, Check, ChevronRight, CircleHelp, Clock3, FileText,
  FlaskConical, Focus, Heart, Lightbulb, LoaderCircle, LockKeyhole, Maximize, MicOff,
  Play, Plus, RotateCcw, ShieldCheck, Sparkles, Square, Sun, Waves, X,
} from "lucide-react";
import { useMeasurement } from "@/lib/use-measurement";
import { clockText, CoachingMode, decisionLabel, Mode, percent, Report } from "@/lib/types";
import { PulseWaveform } from "./pulse-waveform";
import { ReportView } from "./report";
import { FaceHeatmap } from "./face-heatmap";

const sources = { camera: "Live camera", recording: "Video recording", simulation: "Guided simulation" };

function Brand({ compact = false }: { compact?: boolean }) {
  return <div className="brand"><span className="brand-mark"><Activity size={25} strokeWidth={2.1} /></span>{!compact && <span>Pulse<span className="brand-light">Pilot</span></span>}</div>;
}

function FaceGuide({ active }: { active: boolean }) {
  return <svg className={`face-guide ${active ? "active" : ""}`} viewBox="0 0 300 330" fill="none" aria-hidden="true">
    <path className="guide-bracket" d="M65 44H40v35M235 44h25v35M40 250v35h25M260 250v35h-25" />
    <ellipse className="guide-oval" cx="150" cy="148" rx="76" ry="99" />
    <path className="guide-cross" d="M145 41h10M150 36v10M145 255h10M150 250v10" />
    <circle className="guide-dot" cx="150" cy="179" r="3" />
  </svg>;
}

function ConsentDialog({ mode, onClose, onStart, fileName }: {
  mode: Mode; onClose: () => void; onStart: (duration: number, aiConsent: boolean, coaching: CoachingMode, healthAiConsent: boolean, resting: boolean, symptoms: boolean) => void;
  fileName?: string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [duration, setDuration] = useState(60);
  const [symptoms, setSymptoms] = useState(false);
  useEffect(() => {
    const opener = document.activeElement;
    const dialog = dialogRef.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      const target = opener instanceof HTMLElement && opener.isConnected && !opener.matches(":disabled")
        ? opener : document.getElementById("main-content");
      target?.focus({ preventScroll: true });
    };
  }, []);
  return <dialog ref={dialogRef} className="setup-dialog" aria-labelledby="setup-title" onCancel={onClose}>
    <button className="close-button" aria-label="Close setup" onClick={onClose}><X size={20} /></button>
    <div className="dialog-icon">{mode === "simulation" ? <FlaskConical size={25} /> : <Camera size={25} />}</div>
    <h2 id="setup-title">{mode === "simulation" ? "Explore a guided session." : "A moment to get ready."}</h2>
    <p>{mode === "simulation" ? "Watch a reproducible, accelerated scenario with changing light and motion. Every value is synthetic."
      : "Sit comfortably, face a steady light, and keep your whole face in view."}</p>
    {fileName && <div className="file-name"><FileText size={16} /> {fileName}</div>}
    <label className="field-label" htmlFor="duration">Measurement length</label>
    <div className="duration-options" id="duration" role="group" aria-label="Measurement length">
      {[30, 60, 90].map(n => <button key={n} aria-pressed={duration === n} className={duration === n ? "selected" : ""} onClick={() => setDuration(n)}>{n} seconds{n === 60 && <span>Recommended</span>}</button>)}
    </div>
    <span className="field-label">Measurement coaching</span>
    <p><strong>Muse Spark</strong> · Guides your measurement and explains your results.</p>
    {mode !== "simulation" && <>
      <label className="check-label"><input type="checkbox" checked={symptoms} onChange={e => setSymptoms(e.target.checked)} /><span>I am currently experiencing chest pain, severe shortness of breath, or fainting.</span></label>
      {symptoms && <p role="alert">Seek emergency medical help now; call your local emergency number. Do not wait for a measurement or AI response. <a href="https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack" target="_blank" rel="noreferrer">American Heart Association guidance</a></p>}
    </>}
    <button className="primary wide" onClick={() => onStart(duration, true, "meta", true, false, symptoms)}>
      {mode === "simulation" ? <Play size={17} /> : <Camera size={18} />}{mode === "simulation" ? "Start simulated session" : mode === "recording" ? "Process recording" : "Enable camera & start"}
    </button>
  </dialog>;
}

export function PulsePilot() {
  const [view, setView] = useState<"measure" | "reports" | "about">("measure");
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [setup, setSetup] = useState<Mode | null>(null);
  const [file, setFile] = useState<File | undefined>();
  const [showHeatmap, setShowHeatmap] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);
  const captureRef = useRef<HTMLDivElement>(null);
  const latestReportId = useRef<string | null>(null);
  const m = useMeasurement(report => {
    setReports(previous => [report, ...previous.filter(r => r.id !== report.id)].slice(0, 20));
    if (latestReportId.current !== report.id) {
      latestReportId.current = report.id;
      setSelectedReport(report.id);
      setView("reports");
    }
  });
  const busy = ["connecting", "measuring", "finishing"].includes(m.status);
  const measuring = m.status === "measuring";
  const liveVideo = measuring && m.mode !== "simulation";
  const current = measuring ? m.sample : null;
  const displayedBpm = current?.display_bpm !== undefined ? current.display_bpm : current?.bpm;
  const readingState = current?.display_state ?? current?.state;
  const camera = measuring ? m.camera ?? current?.camera : null;
  const faceBox = showHeatmap && m.heatmap ? m.heatmap.bbox : camera?.bbox;
  const active = measuring ? m.interventions.find(i => i.outcome === "observing") : undefined;
  const lastIntervention = measuring ? m.interventions.at(-1) : undefined;
  const selected = reports.find(r => r.id === selectedReport);
  const startSetup = (mode: Mode) => { void m.refreshHealth(); setSetup(mode); };
  const go = (next: typeof view) => { if (busy) return; setView(next); if (next === "reports") setSelectedReport(null); };
  const reset = () => { m.cancel(); setSelectedReport(null); setView("measure"); };
  const conditions = [
    { title: "Face position", icon: Focus, value: !current ? "Waiting" : !current.camera.face_visible ? "Find your face" :
      current.camera.center_offset > .18 || Math.abs(current.camera.yaw_proxy) > .35 ? "Adjust position" : "In position",
      good: current && current.camera.face_visible && current.camera.center_offset <= .18 && Math.abs(current.camera.yaw_proxy) <= .35 },
    { title: "Lighting", icon: Sun, value: !current || !current.camera.face_visible ? "Waiting" :
      current.camera.brightness < 55 ? "More light" : current.camera.light_imbalance > 45 || current.camera.brightness > 225 ? "Adjust lighting" : "Even & bright",
      good: current && current.camera.face_visible && current.camera.brightness >= 55 && current.camera.brightness <= 225 && current.camera.light_imbalance <= 45 },
    { title: "Head movement", icon: Waves, value: !current || !current.camera.face_visible ? "Waiting" : current.camera.motion > .28 ? "Hold steady" : "Steady",
      good: current && current.camera.face_visible && current.camera.motion <= .28 },
  ];
  const guideMessage = m.status === "connecting" ? m.message : m.coachingState === "DECIDING" && measuring ? "Choosing a useful adjustment… Measurement continues." : active?.action ??
    (current?.usable ? "Your signal is settling in. Keep this comfortable position." :
      measuring ? "Face the camera and hold still while we find your pulse signal." :
        "Good measurements start with a comfortable setup.");

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="sidebar">
      <Brand />
      <nav aria-label="Main navigation">
        <button aria-current={view === "measure" ? "page" : undefined} className={view === "measure" ? "nav-item selected" : "nav-item"} onClick={() => go("measure")} disabled={busy && view !== "measure"}><Activity size={18} />Measure<span className="nav-dot" /></button>
        <button aria-current={view === "reports" ? "page" : undefined} className={view === "reports" ? "nav-item selected" : "nav-item"} onClick={() => go("reports")} disabled={busy}><FileText size={18} />Session reports{reports.length > 0 && <span className="nav-count">{reports.length}</span>}</button>
        <button aria-current={view === "about" ? "page" : undefined} className={view === "about" ? "nav-item selected" : "nav-item"} onClick={() => go("about")} disabled={busy}><CircleHelp size={18} />How it works</button>
      </nav>
      <span className="research-badge"><span />Research preview</span>
    </header>
    <div className="workspace">
      <main id="main-content" tabIndex={-1}>
        {view === "measure" && <>
          <div className="page-heading"><div><h1>Estimate your heart rate with your webcam.</h1><p>Get live guidance to improve your signal, then review your heart-rate trends, measurement quality, and session insights.</p></div>
            <button className="service-indicator" onClick={() => void m.refreshHealth()} title="Refresh service status"><span className={m.health ? "online" : ""} />{m.health ? m.health.model_ready ? "Inference ready" : "Service connected" : "Service offline"}<RotateCcw size={12} /></button>
          </div>
          {m.error && <div className="error-banner" role="alert"><div><strong>Let’s get you connected.</strong><p>{m.error}</p></div><button className="secondary small" onClick={() => startSetup(m.mode)}>Try again</button></div>}
          {m.mode === "simulation" && busy && <div className="simulation-banner"><FlaskConical size={17} /><strong>Simulation · {m.playbackRate}× playback</strong> Synthetic values to explore the experience. No camera or physiological measurement.</div>}
          <div className="measurement-grid">
            <div className="capture-column">
              <div className="camera-shell-heading"><span><Camera size={16} />PulsePilot live measurement</span><span>{busy ? sources[m.mode] : "Camera preview"}</span></div>
              <div ref={captureRef} className={`capture-stage ${!busy ? "has-demo" : ""} ${measuring ? "is-measuring" : ""} ${current?.usable ? "is-stable" : ""}`}>
                {!busy && <div className="camera-demo"><Image src="/images/pulsepilot-preview.webp" alt="Illustrative portrait with subtle facial landmarks showing webcam sensing" fill sizes="(max-width: 520px) 650px, (max-width: 1100px) 860px, 70vw" loading="eager" /></div>}
                <video ref={m.videoRef} playsInline muted className={`${m.mode === "camera" ? "mirrored" : ""} ${liveVideo ? "visible" : ""}`} aria-label="Live camera or recording preview" />
                <div className="camera-top"><span className="camera-badge"><span className={measuring ? "live-dot" : "off-dot"} />{measuring ? sources[m.mode] : m.status === "connecting" ? "Connecting" : "Camera off"}</span>
                  <button className="camera-expand" aria-label="Expand camera preview" onClick={() => {
                    if (document.fullscreenElement) void document.exitFullscreen();
                    else void captureRef.current?.requestFullscreen().catch(() => {});
                  }}><Maximize size={17} /></button>
                </div>
                {busy && (!measuring || m.mode === "simulation") && <FaceGuide active={measuring} />}
                {liveVideo && showHeatmap && m.heatmap && (camera?.face_count ?? 0) <= 1 &&
                  <FaceHeatmap heatmap={m.heatmap} captureSize={m.captureSize} mirrored={m.mode === "camera"} />}
                {liveVideo && camera?.face_visible && faceBox && <svg className={`face-overlay ${m.mode === "camera" ? "mirrored" : ""}`} viewBox={`0 0 ${m.captureSize.width} ${m.captureSize.height}`} preserveAspectRatio="xMidYMid meet" aria-label="Detected face" role="img">
                  <rect x={faceBox[0] * m.captureSize.width} y={faceBox[1] * m.captureSize.height} width={(faceBox[2] - faceBox[0]) * m.captureSize.width} height={(faceBox[3] - faceBox[1]) * m.captureSize.height} rx={showHeatmap && m.heatmap ? 0 : 12} fill="none" stroke={showHeatmap && m.heatmap ? "#ff3020" : current?.usable ? "#75e1cf" : "#ffffff"} strokeWidth={showHeatmap && m.heatmap ? 2 : 1.5} />
                  {camera.landmarks.map((p, i) => <circle key={i} cx={p[0] * m.captureSize.width} cy={p[1] * m.captureSize.height} r="2" fill="#b9f1e6" />)}
                </svg>}
                <div className="camera-center-copy">{!busy && <><h2>A small pause.<br />A pulse of insight.</h2><p>Face your camera.<br />We’ll guide you from there.</p><span className="preview-caption"><Focus size={13} />Illustrative preview</span></>}
                  {m.status === "connecting" && <div className="initializing"><LoaderCircle className="spin" size={23} /><span>Preparing your measurement</span></div>}
                </div>
                {liveVideo && <>
                  <div className="heatmap-control" title="FacePhys model attention with pulse-driven highlights, styled after the FacePhys demo. This is a model visualization, not a blood-flow measurement.">
                    <button role="switch" aria-checked={showHeatmap} aria-describedby="heatmap-description" onClick={() => setShowHeatmap(value => !value)}>
                      Face heatmap<span className="heatmap-switch" />
                    </button>
                    <small id="heatmap-description">{!showHeatmap ? "Overlay off" : m.heatmap && (camera?.face_count ?? 0) <= 1 ? camera?.face_visible ? "FacePhys attention" : "Reacquiring face…" : "Waiting for face attention"}</small>
                    {showHeatmap && <span className="heatmap-legend"><span />Low · model attention · high</span>}
                  </div>
                  <div className="camera-reading"><span>Estimated heart rate</span><div><strong>{displayedBpm != null ? displayedBpm.toFixed(1) : "—"}</strong><span>BPM</span></div><span>{readingState ?? "Finding your face"}</span></div>
                </>}
                <div className="camera-bottom"><span><LockKeyhole size={13} />Frames processed, never saved</span><span>{measuring ? `${Math.round(current?.fps ?? 0)} fps` : m.status === "connecting" ? "Preparing camera" : "Camera permission required"}</span></div>
              </div>
              {liveVideo && <div className="camera-signal">
                <div className="camera-signal-heading"><span><Waves size={14} />Live pulse waveform</span><span>{Math.max(0, Math.ceil(m.duration - (current?.t ?? 0)))}s remaining</span></div>
                <PulseWaveform sample={current} active={measuring} label="Pulse waveform below camera preview" />
              </div>}
              <div className="capture-controls">
                <div className="session-length"><Clock3 size={17} /><span>{busy ? <><strong>{clockText(current?.t ?? m.history.at(-1)?.t ?? 0)}</strong> / {clockText(m.duration)}</> : <><strong>60 second</strong> guided session</>}</span></div>
                <div className="control-buttons">{measuring ? <>
                  <button className="secondary small" onClick={m.extend} disabled={m.duration >= 180}><Plus size={16} />30 sec</button><button className="primary" onClick={m.finish}><Square size={13} fill="currentColor" />Finish</button>
                </> : m.status === "connecting" ? <button className="secondary" onClick={m.cancel}>Cancel</button> :
                  m.status === "finishing" ? <button className="primary" disabled><LoaderCircle className="spin" size={16} />Preparing report</button> :
                  <button className="primary" onClick={() => startSetup("camera")}><Camera size={17} />Start measurement</button>}</div>
              </div>
              {busy && <div className="session-progress" role="progressbar" aria-label="Measurement progress" aria-valuenow={Math.round(current?.t ?? 0)} aria-valuemin={0} aria-valuemax={m.duration}><span style={{ width: `${Math.min(100, (current?.t ?? m.history.at(-1)?.t ?? 0) / m.duration * 100)}%` }} /></div>}
              {!liveVideo && <section className="waveform-panel"><div className="section-heading"><h3><Waves size={17} />Your pulse waveform</h3><span>{current?.waveform.length ? "BVP · normalized" : "Waiting for signal"}</span></div>
                <PulseWaveform sample={current} active={measuring} playbackRate={m.playbackRate} label="Live FacePhys blood volume pulse waveform" />
                <div className="waveform-footer"><span>Recent 8 seconds</span><span><span className={`mini-dot ${current?.usable ? "good" : ""}`} />{current?.state ?? "Ready when you are"}</span></div>
              </section>}
            </div>
            <div className="insight-column">
              <section className="heart-panel"><div className="section-heading"><h3>Estimated heart rate</h3><Heart size={19} /></div>
                <div className="heart-value">{displayedBpm ?? <span className="empty-dash">—</span>}<span>BPM</span></div>
                <div className={`measurement-state ${(current?.display_state ? current.display_state.startsWith("10s window") : current?.usable) ? "good" : ""}`}><span />{readingState ?? (m.status === "connecting" ? "Initializing" : "Not measuring")}</div>
                <div className="quality-meter"><div><span>Signal quality</span><strong>{percent(current?.sqi)}</strong></div><div className="meter-track"><span style={{ width: `${(current?.sqi ?? 0) * 100}%` }} /></div><p>{current?.sqi != null ? "Signal periodicity, not an accuracy score." : "We’ll show a number when there’s enough usable signal."}</p></div>
              </section>
              <section className="coach-panel"><div className="section-heading"><h3><Sparkles className="coach-symbol" size={18} />Your measurement coach</h3><span className="live-label">{measuring ? m.coachingMode === "passive" ? "Passive" : m.coachingState.toLowerCase() : "Ready"}</span></div>
                <h2 aria-live="polite">{guideMessage}</h2>
                {active && <small>{decisionLabel(active)}</small>}
                <p>{active?.explanation ?? (active ? "We’ll compare the signal before and after this adjustment." : "Sit at ease. Keep the light in front of you. We’ll help with the rest.")}</p>
                {active ? <div className="intervention-status"><LoaderCircle size={14} className="spin" /><span>{m.coachingState === "ACTING" ? "Time to make your adjustment" : "Comparing measurement conditions after your adjustment"}</span></div> :
                  lastIntervention ? <div className="intervention-status"><Check size={15} /><span>{lastIntervention.outcome === "improved" ? `Periodicity improved by ${Math.round((lastIntervention.delta ?? 0) * 100)} points` : `Last adjustment: ${lastIntervention.outcome}`}</span></div> :
                    <div className="coach-footnote"><ShieldCheck size={14} />One useful adjustment at a time</div>}
              </section>
              <section className="conditions-panel"><h3>Your setup</h3>{conditions.map(({ title, icon: Icon, value, good }) => <div className="condition" key={title}><span><Icon size={16} />{title}</span><span className={good ? "condition-good" : current ? "condition-adjust" : ""}>{good && <Check size={13} />}{value}</span></div>)}</section>
            </div>
          </div>
          <div className="measurement-footnote"><ShieldCheck size={14} /><p>For curiosity, not diagnosis. Signal quality does not guarantee heart-rate accuracy.</p><span>Powered by FacePhys</span></div>
          <input type="file" ref={fileRef} accept="video/*" hidden aria-label="Choose recorded video" onChange={e => { const selected = e.target.files?.[0]; if (selected) { setFile(selected); startSetup("recording"); } e.target.value = ""; }} />
        </>}
        {view === "reports" && (selected ? <ReportView report={selected} onBack={() => setSelectedReport(null)} onNew={reset} /> : <>
          <div className="page-heading"><div><h1>Your moments, measured.</h1><p>Reports from this visit. Closing or refreshing this page clears them.</p></div><button className="primary" onClick={reset}><Plus size={16} />New measurement</button></div>
          {reports.length === 0 ? <div className="empty-reports"><FileText size={40} strokeWidth={1.2} /><h2>Your first report starts with a moment.</h2><p>Complete a measurement to see your heart rate, signal quality, and the difference each adjustment made.</p><button className="primary" onClick={reset}>Go to measurement<ArrowRight size={16} /></button></div> :
            <div className="report-list">{reports.map(report => <button key={report.id} className="report-card" onClick={() => setSelectedReport(report.id)}><div className="report-card-icon">{report.mode === "simulation" ? <FlaskConical /> : <Activity />}</div><div><h3>{report.mode === "simulation" ? "Simulated measurement" : "Heart-rate measurement"}</h3><p>{new Date(report.created_at).toLocaleString()} · {clockText(report.stats.duration)}</p></div><div className="report-card-bpm">{report.stats.mean_bpm ?? "—"}<span>BPM</span></div><span className="report-card-quality">{percent(report.stats.usable_fraction)} usable</span><ChevronRight size={20} /></button>)}</div>}
        </>)}
        {view === "about" && <div className="about-view">
          <header className="about-hero">
            <div className="about-hero-copy"><p className="about-eyebrow"><span aria-hidden="true" />Research prototype</p><h1>How PulsePilot works.</h1><p className="about-lead">A camera. A subtle signal.<br />A clearer view of your recording.</p><p>PulsePilot is a research prototype that estimates your heart rate from webcam video, with live guidance and a report that explains the quality of each recording.</p><div className="about-hero-actions"><button className="primary" onClick={reset}>Start a measurement<ArrowRight size={16} aria-hidden="true" /></button><a className="about-hero-link" href="#measurement-title">Follow the signal<ArrowRight size={18} aria-hidden="true" /></a></div><ul className="about-trust"><li><LockKeyhole size={14} aria-hidden="true" />Frames processed, never saved</li><li><MicOff size={14} aria-hidden="true" />Audio is never captured</li><li><ShieldCheck size={14} aria-hidden="true" />For curiosity, not diagnosis</li></ul></div>
            <figure className="about-visual"><div className="about-face"><FaceGuide active /></div><ArrowRight className="about-visual-arrow" size={22} aria-hidden="true" /><div className="about-signal"><svg className="about-wave" viewBox="0 0 220 72" fill="none" aria-hidden="true"><path className="about-wave-grid" d="M0 18h220M0 36h220M0 54h220" /><path className="about-wave-trace" d="M2 38c10 0 12-2 18-2 8 0 9 14 15 14s7-30 13-30 6 22 12 22 6-6 14-6 10 2 16 2 8-12 14-12 7 26 13 26 6-20 12-20 6 4 14 4 10-2 16-2 8 10 14 10 7-24 13-24 6 18 12 18 6-4 12-4" /></svg><div className="about-readout"><span>Estimated heart rate</span><strong>72.4<small>BPM</small></strong><span className="about-readout-state"><span aria-hidden="true" />Signal settling</span></div></div><figcaption>Facial video to pulse waveform<span>Illustration of the sensing process — not a real reading</span></figcaption></figure>
          </header>
          <nav className="about-nav" aria-label="On this page"><span>On this page</span><a href="#measurement-title">The measurement</a><a href="#architecture-title">Architecture</a><a href="#agents-title">AI guidance</a><a href="#facephys-title">FacePhys model</a><a href="#limits-title">Limitations</a></nav>
          <section className="about-intro" aria-labelledby="measurement-title"><div className="about-section-heading"><p className="about-eyebrow">01 · The measurement</p><h2 id="measurement-title">From camera video to pulse estimates.</h2><p>With each heartbeat, subtle changes in blood volume affect the light reflected by your face. FacePhys looks for that pattern in camera frames to estimate your pulse.</p></div><ol className="about-steps">
            <li><span aria-hidden="true">01</span><div><h3>Capture the signal</h3><p>Your webcam captures facial video. FacePhys extracts a pulse waveform from those frames.</p></div></li>
            <li><span aria-hidden="true">02</span><div><h3>Improve the recording</h3><p>Lighting, motion, and camera timing all matter. PulsePilot offers one correction at a time and compares the signal before and after you adjust.</p></div></li>
            <li><span aria-hidden="true">03</span><div><h3>Review the evidence</h3><p>Your session report brings together heart-rate estimates, signal quality, and recorded adjustments.</p></div></li>
          </ol></section>
          <section className="about-section" aria-labelledby="architecture-title">
            <div className="about-section-heading"><p className="about-eyebrow">02 · Architecture</p><h2 id="architecture-title">The architecture at a glance.</h2></div>
            <p className="about-section-lead">The React / Next.js workspace handles capture, live charts, and report export. A WebSocket connects it to a persistent Python / FastAPI service for sensing and session control.</p>
            <figure className="architecture-diagram">
              <figcaption>Continuous measurement</figcaption>
              <ol className="architecture-flow">{[
                ["Browser capture", "Camera or recorded video"],
                ["FastAPI service", "Timestamped video frames"],
                ["FacePhys / JAX", "Pulse waveform extraction"],
                ["Signal validation", "Heart rate + quality checks"],
                ["Live workspace", "Readings, charts, and report"],
              ].map(([title, detail], i) => <li key={title}><strong>{title}</strong><span>{detail}</span>{i < 4 && <ArrowRight className="flow-arrow" size={18} aria-hidden="true" />}</li>)}</ol>
              <p>Frames are processed by the configured inference service and discarded. Audio is never captured.</p>
            </figure>
            <figure className="architecture-diagram agent-diagram">
              <figcaption>Event-driven guidance</figcaption>
              <ol className="architecture-flow agent-flow">{[
                ["Session context", "Quality, evidence, and history"],
                ["LangGraph + Muse Spark", "Propose or select a response"],
                ["Server validation", "Check identity and evidence"],
                ["Guidance and insights", "Validated result or rules fallback"],
              ].map(([title, detail], i) => <li key={title}><strong>{title}</strong><span>{detail}</span>{i < 3 && <ArrowRight className="flow-arrow" size={18} aria-hidden="true" />}</li>)}</ol>
              <p>Coaching and report events trigger optional model requests while measurement continues. Muse receives numerical summaries and session context; camera images and waveforms stay out of those requests.</p>
            </figure>
          </section>
          <section className="about-section about-agents" aria-labelledby="agents-title">
            <div className="about-section-heading"><p className="about-eyebrow">03 · AI guidance</p><h2 id="agents-title">How the agentic system works.</h2></div>
            <p className="about-section-lead">Three LangGraph workflows coordinate Meta Muse Spark assistance. Each has a defined task, a server validation step, and a deterministic fallback.</p>
            <dl className="agent-workflows">
              <div><dt><Focus size={24} aria-hidden="true" />Measurement coach</dt><dd>Uses lighting, motion, face position, and recent adjustment outcomes. In the default assist mode, rules choose the action and Muse can explain it. Adaptive mode lets Muse propose a choice from the currently eligible actions.</dd></div>
              <div><dt><FileText size={24} aria-hidden="true" />Session analyst</dt><dd>Selects report claims tied to measured statistics and recorded adjustments. The server checks each claim against its evidence and renders the factual text.</dd></div>
              <div><dt><Sparkles size={24} aria-hidden="true" />Health Insights</dt><dd>Selects from server-authored guidance using measurement quality and supplied activity or symptom context. Evidence checks determine which guidance is eligible.</dd></div>
            </dl>
            <p className="architecture-note">The server controls measurement thresholds and adjustment timing. Invalid or late AI responses fall back to rules. The numerical report arrives before optional AI analysis, and sensing, coaching, and reports remain available when AI is unavailable.</p>
          </section>
          <section className="about-section" aria-labelledby="facephys-title">
            <div className="about-section-heading"><p className="about-eyebrow">04 · FacePhys model</p><h2 id="facephys-title">Inside the FacePhys model.</h2></div>
            <p className="about-section-lead">FacePhys learns an evolving pulse state from facial video. Its temporal-spatial state-space duality combines 2D convolutions for spatial features with a state-space model for changes over time.</p>
            <figure className="architecture-diagram model-diagram">
              <figcaption>Simplified streaming model</figcaption>
              <ol className="architecture-flow model-flow">{[
                ["Face crop", "36 × 36 RGB input"],
                ["Spatial + temporal blocks", "Normalization, 2D convolutions, and state-space updates"],
                ["Pooling + prediction head", "Combine features into a pulse estimate"],
                ["Pulse waveform", "One BVP output per frame"],
              ].map(([title, detail], i) => <li key={title}><strong>{title}</strong><span>{detail}</span>{i < 3 && <ArrowRight className="flow-arrow" size={18} aria-hidden="true" />}</li>)}</ol>
              <p className="model-state"><RotateCcw size={18} aria-hidden="true" />Updated state carries temporal information into the next frame.</p>
            </figure>
            <div className="model-explanation"><p>Temporal normalization reduces drift and standardizes changing features. Complex-valued state transitions represent rhythmic patterns. Reusing the state supports frame-by-frame inference without retaining an ever-growing video history.</p><p>PulsePilot runs the pretrained <strong>FacePhys.rlap</strong> checkpoint in Python / JAX at a 30 Hz model cadence, without retraining. PulsePilot then uses a ten-second waveform window and quality checks to derive heart-rate estimates.</p></div>
            <p className="architecture-source">Model schematic summarized from Figure 3 and Sections 3.1–3.5 of <a href="https://arxiv.org/html/2512.06275v1#S3" target="_blank" rel="noreferrer">FacePhys: State of the Heart Learning (Wang et al., 2025)</a>. Integration details follow the <a href="https://github.com/KegangWangCCNU/open-rppg/tree/4d24237e7b14e17429b49d0334f2282b7d2fd159" target="_blank" rel="noreferrer">pinned open-rPPG implementation</a>.</p>
          </section>
          <section className="about-limits" aria-labelledby="limits-title"><Lightbulb size={24} aria-hidden="true" /><div><h2 id="limits-title">A good signal is only part of the picture.</h2><p>This research prototype has not been clinically validated. A steady waveform or high signal-quality score does not prove an accurate heart rate. Reports do not diagnose conditions, and changes in the estimates are not confirmed physiological changes.</p><p>Head angle and visibility are approximated from six face landmarks. SAM segmentation is not used in this version. Synthetic demos test the software experience, not sensing accuracy.</p></div></section>
          <div className="about-cta"><div><h2>Find your steady signal.</h2><p>Start with a comfortable seat and light in front of you.</p></div><button className="primary" onClick={reset}>Try a measurement<ArrowRight size={16} aria-hidden="true" /></button></div>
        </div>}
      </main>
    </div>
    {setup && <ConsentDialog mode={setup} fileName={setup === "recording" ? file?.name : undefined}
      onClose={() => setSetup(null)} onStart={(duration, aiConsent, coaching, healthAiConsent, resting, symptoms) => {
        const mode = setup; setSetup(null);
        void m.start({ mode, duration, aiConsent, coaching, healthAiConsent,
          healthContext: { activity: resting ? "resting" : "unknown", concerning_symptoms: symptoms }, frameConsent: mode !== "simulation", file });
      }} />}
  </div>;
}
