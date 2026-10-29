"use client";

import { useEffect, useRef, useState } from "react";
import {
  Activity, ArrowRight, Camera, Check, ChevronRight, CircleHelp, Clock3, FileText,
  FlaskConical, Focus, Heart, Lightbulb, LoaderCircle, LockKeyhole, Maximize,
  Play, Plus, RotateCcw, ShieldCheck, Sparkles, Square, Sun, Upload, Waves, X,
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
    <path className="guide-person" d="M122 243v16c-40 6-67 22-80 44M178 243v16c40 6 67 22 80 44M117 137h15M168 137h15M150 146v27l-9 5M130 201q20 10 40 0" />
    <path className="guide-cross" d="M145 41h10M150 36v10M145 255h10M150 250v10" />
    <circle className="guide-dot" cx="150" cy="179" r="3" />
  </svg>;
}

function ConsentDialog({ mode, onClose, onStart, aiAvailable, fileName }: {
  mode: Mode; onClose: () => void; onStart: (duration: number, aiConsent: boolean, coaching: CoachingMode, healthAiConsent: boolean, resting: boolean, symptoms: boolean) => void;
  aiAvailable: boolean; fileName?: string;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [duration, setDuration] = useState(60);
  const [consent, setConsent] = useState(false);
  const [aiConsent, setAiConsent] = useState(false);
  const [healthAiConsent, setHealthAiConsent] = useState(false);
  const [resting, setResting] = useState(false);
  const [symptoms, setSymptoms] = useState(false);
  const [coaching, setCoaching] = useState<CoachingMode>("meta");
  useEffect(() => { dialogRef.current?.showModal(); }, []);
  return <dialog ref={dialogRef} className="setup-dialog" onCancel={onClose}>
    <button className="close-button" aria-label="Close setup" onClick={onClose}><X size={20} /></button>
    <div className="dialog-icon">{mode === "simulation" ? <FlaskConical size={25} /> : <Camera size={25} />}</div>
    <h2>{mode === "simulation" ? "Explore a guided session." : "A moment to get ready."}</h2>
    <p>{mode === "simulation" ? "Watch a reproducible, accelerated scenario with changing light and motion. Every value is synthetic."
      : "Sit comfortably, face a steady light, and keep your whole face in view."}</p>
    {fileName && <div className="file-name"><FileText size={16} /> {fileName}</div>}
    <label className="field-label" htmlFor="duration">Measurement length</label>
    <div className="duration-options" id="duration" role="group" aria-label="Measurement length">
      {[30, 60, 90].map(n => <button key={n} className={duration === n ? "selected" : ""} onClick={() => setDuration(n)}>{n} seconds{n === 60 && <span>Recommended</span>}</button>)}
    </div>
    <label className="field-label" htmlFor="coaching-mode">Measurement coaching</label>
    <select id="coaching-mode" value={coaching} onChange={e => setCoaching(e.target.value as CoachingMode)}>
      <option value="meta">Muse Spark · validated guidance with your consent</option>
      <option value="rules">Rules · deterministic guidance</option>
      <option value="passive">Passive · observe without instructions</option>
    </select>
    {mode !== "simulation" && <label className="check-label"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span>I agree to send video frames to the inference service for this measurement.<small>Frames are processed in memory and discarded. Audio is never captured. Reports stay in this page until exported.</small></span></label>}
    <label className={`check-label ${!aiAvailable ? "disabled" : ""}`}><input type="checkbox" checked={aiConsent} disabled={!aiAvailable} onChange={e => setAiConsent(e.target.checked)} /><span>Let Muse Spark assist with guidance and interpret my measurement metrics.<small>{aiAvailable ? "Only numerical summaries and guidance history go to Meta. No images. Without consent, Muse mode uses rules." : "Available when a Meta API key is configured and agents are enabled. Deterministic guidance and reports work now."}</small></span></label>
    {mode !== "simulation" && <>
      <label className="check-label"><input type="checkbox" checked={resting} onChange={e => setResting(e.target.checked)} /><span>This measurement is at rest: calm, seated or lying down, and not exercising.<small>Optional context; otherwise activity remains unknown.</small></span></label>
      <label className="check-label"><input type="checkbox" checked={symptoms} onChange={e => setSymptoms(e.target.checked)} /><span>I am currently experiencing chest pain, severe shortness of breath, or fainting.</span></label>
      {symptoms && <p role="alert">Seek emergency medical help now; call your local emergency number. Do not wait for a measurement or AI response. <a href="https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack" target="_blank" rel="noreferrer">American Heart Association guidance</a></p>}
    </>}
    <label className={`check-label ${!aiAvailable ? "disabled" : ""}`}><input type="checkbox" checked={healthAiConsent} disabled={!aiAvailable} onChange={e => setHealthAiConsent(e.target.checked)} /><span>Allow Muse Spark to select Health Insights for this report.<small>Separate consent: send accepted heart-rate statistics, signal quality, measurement source, and any activity or symptom context above to Meta. No images or saved health history. Without consent, Health Insights use deterministic guidance.</small></span></label>
    <button className="primary wide" disabled={mode !== "simulation" && !consent} onClick={() => onStart(duration, aiConsent, coaching, healthAiConsent, resting, symptoms)}>
      {mode === "simulation" ? <Play size={17} /> : <Camera size={18} />}{mode === "simulation" ? "Start simulated session" : mode === "recording" ? "Process recording" : "Enable camera & start"}
    </button>
    <p className="dialog-footnote">For research and personal observation. Not a medical device.</p>
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
    <aside className="sidebar">
      <Brand />
      <div className="workspace-label">Your measurement space</div>
      <nav aria-label="Main navigation">
        <button className={view === "measure" ? "nav-item selected" : "nav-item"} onClick={() => go("measure")} disabled={busy && view !== "measure"}><Activity size={19} />Measure<span className="nav-dot" /></button>
        <button className={view === "reports" ? "nav-item selected" : "nav-item"} onClick={() => go("reports")} disabled={busy}><FileText size={19} />Session reports{reports.length > 0 && <span className="nav-count">{reports.length}</span>}</button>
        <button className={view === "about" ? "nav-item selected" : "nav-item"} onClick={() => go("about")} disabled={busy}><CircleHelp size={19} />How it works</button>
      </nav>
      <div className="sidebar-bottom"><div className="privacy-note"><ShieldCheck size={24} /><strong>Just you. Just this moment.</strong><p>No saved video. No audio.<br />You control every measurement.</p></div>
        <div className="sidebar-footer"><span className="tiny-logo"><Activity size={14} /></span>Built for a steadier signal<span>v0.1</span></div>
      </div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="breadcrumb"><span>PulsePilot</span><ChevronRight size={14} />{view === "measure" ? "Live measurement" : view === "reports" ? "Session reports" : "How it works"}</div>
        <div className="topbar-right"><span className="research-badge"><span />Research preview</span><button className="icon-button" aria-label="How PulsePilot works" disabled={busy} onClick={() => go("about")}><CircleHelp size={19} /></button></div>
      </header>
      <main>
        {view === "measure" && <>
          <div className="page-heading"><div><h1>Find your steady signal.</h1><p>A quiet moment, your camera, and a little guidance.</p></div>
            <button className="service-indicator" onClick={() => void m.refreshHealth()} title="Refresh service status"><span className={m.health ? "online" : ""} />{m.health ? m.health.model_ready ? "Inference ready" : "Service connected" : "Service offline"}<RotateCcw size={12} /></button>
          </div>
          {m.error && <div className="error-banner" role="alert"><div><strong>Let’s get you connected.</strong><p>{m.error}</p></div><button className="secondary small" onClick={() => startSetup(m.mode)}>Try again</button></div>}
          {m.mode === "simulation" && busy && <div className="simulation-banner"><FlaskConical size={17} /><strong>Simulation · {m.playbackRate}× playback</strong> Synthetic values to explore the experience. No camera or physiological measurement.</div>}
          <div className="measurement-grid">
            <div className="capture-column">
              <div className="camera-shell-heading"><span><Camera size={16} />PulsePilot live measurement</span><span>{busy ? sources[m.mode] : "Camera preview"}</span></div>
              <div ref={captureRef} className={`capture-stage ${measuring ? "is-measuring" : ""} ${current?.usable ? "is-stable" : ""}`}>
                <video ref={m.videoRef} playsInline muted className={`${m.mode === "camera" ? "mirrored" : ""} ${liveVideo ? "visible" : ""}`} aria-label="Live camera or recording preview" />
                <div className="camera-grid" />
                <div className="camera-top"><span className="camera-badge"><span className={measuring ? "live-dot" : "off-dot"} />{measuring ? sources[m.mode] : m.status === "connecting" ? "Connecting" : "Camera off"}</span>
                  <button className="camera-expand" aria-label="Expand camera preview" onClick={() => {
                    if (document.fullscreenElement) void document.exitFullscreen();
                    else void captureRef.current?.requestFullscreen().catch(() => {});
                  }}><Maximize size={17} /></button>
                </div>
                {(!measuring || m.mode === "simulation") && <FaceGuide active={measuring} />}
                {liveVideo && showHeatmap && m.heatmap && (camera?.face_count ?? 0) <= 1 &&
                  <FaceHeatmap heatmap={m.heatmap} captureSize={m.captureSize} mirrored={m.mode === "camera"} />}
                {liveVideo && camera?.face_visible && faceBox && <svg className={`face-overlay ${m.mode === "camera" ? "mirrored" : ""}`} viewBox={`0 0 ${m.captureSize.width} ${m.captureSize.height}`} preserveAspectRatio="xMidYMid meet" aria-label="Detected face" role="img">
                  <rect x={faceBox[0] * m.captureSize.width} y={faceBox[1] * m.captureSize.height} width={(faceBox[2] - faceBox[0]) * m.captureSize.width} height={(faceBox[3] - faceBox[1]) * m.captureSize.height} rx={showHeatmap && m.heatmap ? 0 : 12} fill="none" stroke={showHeatmap && m.heatmap ? "#ff3020" : current?.usable ? "#75e1cf" : "#ffffff"} strokeWidth={showHeatmap && m.heatmap ? 2 : 1.5} />
                  {camera.landmarks.map((p, i) => <circle key={i} cx={p[0] * m.captureSize.width} cy={p[1] * m.captureSize.height} r="2" fill="#b9f1e6" />)}
                </svg>}
                <div className="camera-center-copy">{!busy && <><h2>A small pause.<br />A pulse of insight.</h2><p>Position your face inside the guide to begin.</p></>}
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
                  <div className="camera-reading"><span>Estimated heart rate</span><div><strong>{current?.usable && current.bpm != null ? current.bpm.toFixed(1) : "—"}</strong><span>BPM</span></div><span>{current?.state ?? "Finding your face"}</span></div>
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
                <div className="heart-value">{current?.bpm ?? <span className="empty-dash">—</span>}<span>BPM</span></div>
                <div className={`measurement-state ${current?.usable ? "good" : ""}`}><span />{current?.state ?? (m.status === "connecting" ? "Initializing" : "Not measuring")}</div>
                <div className="quality-meter"><div><span>Signal quality</span><strong>{percent(current?.sqi)}</strong></div><div className="meter-track"><span style={{ width: `${(current?.sqi ?? 0) * 100}%` }} /></div><p>{current?.sqi != null ? "Signal periodicity, not an accuracy score." : "We’ll show a number when there’s enough usable signal."}</p></div>
              </section>
              <section className="coach-panel"><div className="section-heading"><h3><span className="coach-symbol">✳</span>Your measurement coach</h3><span className="live-label">{measuring ? m.coachingMode === "passive" ? "Passive" : m.coachingState.toLowerCase() : "Ready"}</span></div>
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
          <div className="explore-row"><div><div className="explore-icon"><FlaskConical size={20} /></div><div><strong>Curious before turning on your camera?</strong><p>Explore a simulated session or use a recording you already have.</p></div></div>
            <div className="explore-actions"><button className="text-button" disabled={busy} onClick={() => fileRef.current?.click()}><Upload size={15} />Use a recording</button><button className="secondary" disabled={busy} onClick={() => startSetup("simulation")}>Explore the demo<ArrowRight size={16} /></button></div>
          </div>
          <div className="measurement-footnote"><ShieldCheck size={14} /><p>For curiosity, not diagnosis. Signal quality does not guarantee heart-rate accuracy.</p><span>Powered by FacePhys</span></div>
          <input type="file" ref={fileRef} accept="video/*" hidden aria-label="Choose recorded video" onChange={e => { const selected = e.target.files?.[0]; if (selected) { setFile(selected); startSetup("recording"); } e.target.value = ""; }} />
        </>}
        {view === "reports" && (selected ? <ReportView report={selected} onBack={() => setSelectedReport(null)} onNew={reset} /> : <>
          <div className="page-heading"><div><h1>Your moments, measured.</h1><p>Reports from this visit. Closing or refreshing this page clears them.</p></div><button className="primary" onClick={reset}><Plus size={16} />New measurement</button></div>
          {reports.length === 0 ? <div className="empty-reports"><FileText size={40} strokeWidth={1.2} /><h2>Your first report starts with a moment.</h2><p>Complete a measurement to see your heart rate, signal quality, and the difference each adjustment made.</p><button className="primary" onClick={reset}>Go to measurement<ArrowRight size={16} /></button></div> :
            <div className="report-list">{reports.map(report => <button key={report.id} className="report-card" onClick={() => setSelectedReport(report.id)}><div className="report-card-icon">{report.mode === "simulation" ? <FlaskConical /> : <Activity />}</div><div><h3>{report.mode === "simulation" ? "Simulated measurement" : "Heart-rate measurement"}</h3><p>{new Date(report.created_at).toLocaleString()} · {clockText(report.stats.duration)}</p></div><div className="report-card-bpm">{report.stats.mean_bpm ?? "—"}<span>BPM</span></div><span className="report-card-quality">{percent(report.stats.usable_fraction)} usable</span><ChevronRight size={20} /></button>)}</div>}
        </>)}
        {view === "about" && <div className="about-view"><div className="page-heading"><div><h1>A pulse, seen in a new light.</h1><p>What PulsePilot measures, and what it can’t tell you.</p></div></div>
          <div className="about-intro"><div className="about-visual"><FaceGuide active /></div><div><h2>Small changes.<br />A signal worth understanding.</h2><p>With each heartbeat, subtle changes in blood volume affect the light reflected by your face. FacePhys looks for that pattern in camera frames to estimate your pulse.</p><p>Lighting, motion, and camera timing all matter. PulsePilot checks those conditions, offers one correction at a time, and compares the signal before and after you adjust.</p></div></div>
          <div className="about-steps">{[
            [Camera, "Capture with consent", "Your browser sends frames to the inference service. Audio is never captured, and raw frames are not saved."],
            [Focus, "Find a usable signal", "The frozen FacePhys model extracts a pulse waveform. Camera checks and signal periodicity decide whether to display an estimate."],
            [Sparkles, "Understand the session", "Reports use measured statistics and recorded interventions. Muse Spark can interpret numerical evidence when configured and you opt in."],
          ].map(([Icon, title, text], i) => { const Component = Icon as typeof Camera; return <section key={i}><Component size={24} /><h3>{title as string}</h3><p>{text as string}</p></section>; })}</div>
          <section className="about-limits"><Lightbulb size={22} /><div><h3>A good signal is only part of the picture.</h3><p>This research prototype has not been clinically validated. A steady waveform or high signal-quality score does not prove an accurate heart rate. Reports do not diagnose conditions, and changes in the estimates are not confirmed physiological changes.</p><p>Head angle and visibility are approximated from six face landmarks. SAM segmentation is not used in this version. Synthetic demos test the software experience, not sensing accuracy.</p></div></section>
          <button className="primary" onClick={reset}>Try a measurement<ArrowRight size={16} /></button>
        </div>}
      </main>
    </div>
    {setup && <ConsentDialog mode={setup} aiAvailable={!!m.health?.ai_configured && m.health.agent_mode !== "off"} fileName={setup === "recording" ? file?.name : undefined}
      onClose={() => setSetup(null)} onStart={(duration, aiConsent, coaching, healthAiConsent, resting, symptoms) => {
        const mode = setup; setSetup(null);
        void m.start({ mode, duration, aiConsent, coaching, healthAiConsent,
          healthContext: { activity: resting ? "resting" : "unknown", concerning_symptoms: symptoms }, frameConsent: mode !== "simulation", file });
      }} />}
  </div>;
}
