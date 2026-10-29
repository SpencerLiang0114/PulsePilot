"use client";

import { ArrowLeft, Download, Printer, CircleCheck, FlaskConical } from "lucide-react";
import { Chart } from "./chart";
import { Analysis, clockText, decisionLabel, percent, Report as ReportData } from "@/lib/types";

export function ReportView({ report, onBack, onNew }: { report: ReportData; onBack: () => void; onNew: () => void }) {
  const { stats } = report;
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `pulsepilot-${report.mode}-${report.id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  const sections: [keyof Analysis, string][] = [
    ["summary", "Your heart rate, in context"], ["quality", "How the measurement held up"],
    ["interventions", "What changed with guidance"], ["recommendations", "For your next measurement"],
  ];
  return <div className="report-view">
    <div className="report-toolbar"><button className="text-button" onClick={onBack}><ArrowLeft size={16} /> All reports</button>
      <div><button className="secondary small" onClick={download}><Download size={15} /> Export JSON</button><button className="secondary small" onClick={() => window.print()}><Printer size={15} /> Print report</button></div>
    </div>
    {report.mode === "simulation" && <div className="simulation-banner"><FlaskConical size={17} /><strong>Simulated session</strong> Synthetic data for exploring the experience. These are not your measurements.</div>}
    <header className="report-heading"><div><div className="completion-label"><CircleCheck size={18} /> Measurement complete</div>
      <h1>A clearer picture of<br />your measurement.</h1>
      <p>{new Date(report.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} <span className="separator">/</span> {clockText(stats.duration)} session <span className="separator">/</span> {report.mode === "camera" ? "Live camera" : report.mode === "recording" ? "Video recording" : "Simulation"}</p></div>
      <div className="report-main-number"><span>Average estimated heart rate</span><div>{stats.mean_bpm ?? "—"} <small>BPM</small></div><p>{stats.mean_bpm == null ? "Insufficient usable signal" : "From accepted measurement windows"}</p></div>
    </header>
    <div className="report-stats">
      <div><span>Median heart rate</span><strong>{stats.median_bpm ?? "—"} <small>BPM</small></strong></div>
      <div><span>Observed range</span><strong>{stats.min_bpm == null ? "—" : `${stats.min_bpm}–${stats.max_bpm}`} <small>BPM</small></strong></div>
      <div><span>Usable windows</span><strong>{percent(stats.usable_fraction)}</strong></div>
      <div><span>First stable signal</span><strong>{stats.stable_at == null ? "—" : clockText(stats.stable_at)}</strong></div>
    </div>
    <div className="report-charts">
      <section className="panel"><div className="section-heading"><h3>Heart rate over time</h3><span>Accepted estimates · BPM</span></div>
        <Chart values={report.samples.map(s => s.bpm)} times={report.samples.map(s => s.t)} label="Accepted heart-rate estimates over the session" unit="BPM" height={150} showScale domain={[Math.max(40, Math.floor((stats.min_bpm ?? 60) / 10) * 10 - 10), Math.min(180, Math.ceil((stats.max_bpm ?? 90) / 10) * 10 + 10)]} empty="No accepted heart-rate windows" />
        <div className="axis"><span>0:00</span><span>{clockText(stats.duration)}</span></div>
      </section>
      <section className="panel"><div className="section-heading"><h3>Signal quality over time</h3><span>Periodicity · %</span></div>
        <Chart values={report.samples.map(s => s.sqi == null ? null : s.sqi * 100)} times={report.samples.map(s => s.t)} label="Signal periodicity over the session" unit="%" domain={[0, 100]} height={150} showScale />
        <div className="axis"><span>0:00</span><span>{clockText(stats.duration)}</span></div>
      </section>
    </div>
    <div className="analysis-heading"><div className="coach-symbol">✳</div><div><h2>Measurement analysis</h2><p>
      {report.analyst === "muse" ? "Selected by Muse Spark from server-validated session evidence" :
        report.ai_status === "pending" ? "Numerical report ready. Muse Spark is preparing its interpretation…" :
        report.ai_status === "unavailable" ? "Muse Spark was unavailable. Showing evidence-based deterministic analysis." :
        report.ai_status === "cancelled" ? "AI interpretation was stopped. Showing evidence-based deterministic analysis." :
        "Evidence-based deterministic analysis. Muse Spark was not used."}
    </p></div></div>
    <div className="analysis-sections">{sections.map(([key, title], index) => <section key={key} className="analysis-section">
      <div className="section-index">{index + 1}</div><div><h3>{title}</h3>
        {report.analysis[key].map((item, i) => <div className="statement" key={i}><p>{item.text}</p>
          <details><summary>{item.kind === "fact" ? "Measured evidence" : item.kind === "limitation" ? "Limitations" : "Possible explanation"} <span>View source</span></summary>
            {item.evidence_ids.map(id => <p key={id}>{report.evidence[id]}</p>)}
          </details></div>)}
      </div>
    </section>)}</div>
    {report.interventions.length > 0 && <section className="panel intervention-report"><h3>Guidance & observed outcomes</h3>
      <p>Observed before/after comparisons do not establish causal benefit or heart-rate accuracy.</p>
      {report.interventions.map(item => <div className="intervention-row" key={item.id}><span>{clockText(item.started_at)}{item.evaluated_at != null && <>–{clockText(item.evaluated_at)}</>}</span><div><strong>{item.action}</strong><p>{decisionLabel(item)}</p><p>{item.before_sqi == null || item.after_sqi == null ? "Not enough comparable signal" : `Periodicity: ${percent(item.before_sqi)} → ${percent(item.after_sqi)}. Change: ${Math.round(item.delta! * 100)} percentage points.`}</p><p>Usable windows: {percent(item.before_usable)} → {percent(item.after_usable)}</p></div><span className={`outcome ${item.outcome}`}>{item.outcome}</span></div>)}
    </section>}
    <div className="quality-detail"><span>Face tracking <strong>{percent(stats.tracking_fraction)}</strong></span><span>Mean capture rate <strong>{stats.mean_fps} fps</strong></span><span>Signal coverage <strong>{percent(stats.signal_coverage)}</strong></span></div>
    {report.capture_diagnostics && <details className="panel">
      <summary>Capture & delivery diagnostics</summary>
      <p>{report.capture_diagnostics.width} × {report.capture_diagnostics.height} capture. Camera track reports {report.capture_diagnostics.track_fps?.toFixed(1) ?? "unavailable"} fps.</p>
      <p>Observed video callbacks: {report.capture_diagnostics.callback_fps?.toFixed(1) ?? "—"} fps. Submitted frames: {report.capture_diagnostics.sent_fps?.toFixed(1) ?? "—"} fps. Server-processed capture: {stats.mean_fps} fps.</p>
      <p>{report.capture_diagnostics.frames_acknowledged} / {report.capture_diagnostics.frames_sent} submitted frames acknowledged. Mean / maximum acknowledgement round trip: {report.capture_diagnostics.mean_ack_round_trip_ms?.toFixed(1) ?? "—"} / {report.capture_diagnostics.max_ack_round_trip_ms?.toFixed(1) ?? "—"} ms.</p>
      <p>Mean / maximum sample frame age at receipt: {report.capture_diagnostics.mean_sample_frame_age_ms?.toFixed(1) ?? "—"} / {report.capture_diagnostics.max_sample_frame_age_ms?.toFixed(1) ?? "—"} ms. Maximum sample arrival gap: {report.capture_diagnostics.max_sample_gap_ms?.toFixed(1) ?? "—"} ms.</p>
      <p>Browser observations measure callbacks and delivery, including encoding and server work. Camera settings are reported by the track. These are not model-only throughput or reference-device accuracy measurements. Per-sample server processing time and inference timeline lag are included in the JSON export.</p>
    </details>}
    <footer className="report-footer"><p>Signal quality describes the measurement, not your health. Accuracy has not been verified against a reference device.</p><button className="primary" onClick={onNew}>Start a new measurement</button></footer>
  </div>;
}
