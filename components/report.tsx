"use client";

import { ArrowLeft, Download, Printer, CircleCheck, FlaskConical } from "lucide-react";
import { Chart } from "./chart";
import { Analysis, HealthInsightBundle, clockText, decisionLabel, percent, Report as ReportData } from "@/lib/types";

function HealthInsights({ bundle }: { bundle: HealthInsightBundle | null | undefined }) {
  if (!bundle) return <section aria-label="Health Insights" className="report-section health-insights">
    <header className="report-section-heading"><h2>Health Insights</h2><p>Suggestions and limitations based on the available session evidence.</p></header>
    <div className="panel"><p>Health Insights are unavailable for this report.</p></div>
  </section>;
  return <section aria-label="Health Insights" className="report-section health-insights">
    <header className="report-section-heading"><h2>Health Insights</h2>
    <p role="status">{bundle.status === "pending" ? "Muse Spark selection pending. Deterministic guidance is available below." :
      bundle.status === "unavailable" ? "AI selection unavailable or stopped. Deterministic guidance remains available." :
      bundle.status === "fallback" ? "Muse Spark could not provide a valid selection. Showing deterministic guidance." :
      bundle.analyst === "muse" ? "AI-selected suggestions · server-authored and validated" : "Deterministic suggestions · Muse Spark was not used for the displayed guidance"}</p></header>
    <div className="panel">
    {!bundle.sufficient_evidence && <p><strong>Insufficient evidence for personal heart-rate interpretation.</strong></p>}
    {[...bundle.insights, ...bundle.limitations].map(item => <article key={item.insight_id} className="statement">
      <h3>{item.title}</h3><p>{item.text}</p>
      <details open={item.insight_id === "urgent"}><summary>Why this appears · evidence &amp; guidance</summary>
        {item.evidence_ids.length === 0 && <p>General wellness education; not inferred from your measurement.</p>}
        {item.evidence_ids.map(id => <p key={id}>{bundle.evidence[id]}</p>)}
        {item.guidance_reference_ids.map(id => {
          const ref = bundle.guidance_references[id];
          return ref && <p key={id}>{ref.url ? <a href={ref.url} target="_blank" rel="noreferrer">{ref.title}</a> : ref.title}</p>;
        })}
      </details>
    </article>)}
    </div>
  </section>;
}

export function ReportView({ report, onBack, onNew }: { report: ReportData; onBack: () => void; onNew: () => void }) {
  const { stats } = report;
  const accepted = report.samples.map(s => s.usable ? s.bpm : null);
  const preliminary = report.samples.map(s => s.usable ? null : s.report_bpm ?? null);
  const plotted = [...accepted, ...preliminary].filter((v): v is number => v != null);
  const preliminaryCount = preliminary.filter(v => v != null).length;
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `pulsepilot-${report.mode}-${report.id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  const sections: [keyof Analysis, string][] = [
    ["summary", "What this means"], ["recommendations", "What to do next"],
  ];
  return <div className="report-view">
    <div className="report-toolbar"><button className="text-button" onClick={onBack}><ArrowLeft size={16} /> All reports</button>
      <div><button className="secondary small" onClick={download}><Download size={15} /> Export JSON</button><button className="secondary small" onClick={() => window.print()}><Printer size={15} /> Print report</button></div>
    </div>
    {report.mode === "simulation" && <div className="simulation-banner"><FlaskConical size={17} /><strong>Simulated session</strong> Synthetic data for exploring the experience. These are not your measurements.</div>}
    <header className="report-heading"><div>
      <h1>Session report</h1>
      <div className="completion-label"><CircleCheck size={18} /> Measurement complete</div>
      <p>{new Date(report.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} <span className="separator">/</span> {clockText(stats.duration)} session <span className="separator">/</span> {report.mode === "camera" ? "Live camera" : report.mode === "recording" ? "Video recording" : "Simulation"}</p></div>
      <div className="report-main-number"><span>Average estimated heart rate</span><div>{stats.mean_bpm ?? "—"} <small>BPM</small></div><p>{stats.mean_bpm == null ? "Insufficient usable signal" : "From accepted measurement windows"}</p></div>
    </header>
    <div className="report-stats">
      <div><span>Median heart rate</span><strong>{stats.median_bpm ?? "—"} <small>BPM</small></strong></div>
      <div><span>Observed range</span><strong>{stats.min_bpm == null ? "—" : `${stats.min_bpm}–${stats.max_bpm}`} <small>BPM</small></strong></div>
      <div><span>Accepted readings</span><strong>{percent(stats.usable_fraction)}</strong></div>
      <div><span>First stable signal</span><strong>{stats.stable_at == null ? "—" : clockText(stats.stable_at)}</strong></div>
    </div>
    <section className="report-section">
    <header className="report-section-heading"><h2>Your results</h2><p>
      {report.analyst === "muse" ? "Selected by Muse Spark from server-validated session evidence" :
        report.ai_status === "pending" ? "Numerical report ready. Muse Spark is preparing its interpretation…" :
        report.ai_status === "unavailable" ? "Muse Spark was unavailable. Showing evidence-based deterministic analysis." :
        report.ai_status === "cancelled" ? "AI interpretation was stopped. Showing evidence-based deterministic analysis." :
        "Evidence-based deterministic analysis. Muse Spark was not used."}
    </p></header>
    <div className="panel analysis-sections">{sections.map(([key, title]) => <section key={key} className="analysis-section">
      <div><h3>{title}</h3>
        {report.analysis[key].map((item, i) => <div className="statement" key={i}><p>{item.text}</p>
          <details><summary>{item.kind === "fact" ? "View measured evidence" : item.kind === "limitation" ? "View limitations" : "View possible explanation"}</summary>
            {item.evidence_ids.map(id => <p key={id}>{report.evidence[id]}</p>)}
          </details></div>)}
      </div>
    </section>)}</div>
    </section>
    <section className="report-section">
    <header className="report-section-heading"><h2>Measurement timeline</h2><p>Heart-rate estimates and signal quality throughout your session.</p></header>
    <div className="panel report-charts">
      <section><div className="section-heading"><h3>Heart rate over time</h3><span>Estimates · BPM</span></div>
        <Chart values={accepted} preliminary={preliminary} times={report.samples.map(s => s.t)} label="Accepted and preliminary heart-rate estimates over the session" unit="BPM" height={150} showScale domain={[Math.max(40, Math.floor((plotted.length ? Math.min(...plotted) : 60) / 10) * 10 - 10), Math.min(180, Math.ceil((plotted.length ? Math.max(...plotted) : 90) / 10) * 10 + 10)]} empty="No heart-rate windows passed the report checks" />
        <div className="axis"><span>0:00</span><span>{clockText(stats.duration)}</span></div>
        <p className="trend-legend"><span>● Accepted</span><span>○ Preliminary · amber, dashed</span></p>
        <p className="trend-note">{accepted.filter(v => v != null).length} accepted · {preliminaryCount} preliminary windows. Only accepted readings contribute to the averages.</p>
        <details className="trend-note"><summary>How to read this chart</summary><p>Preliminary estimates use lower signal-quality and frame-rate thresholds and are excluded from the averages above. Gaps mean no eligible estimate; no values are filled in.</p></details>
        {report.evidence.report_trend && <details className="trend-note"><summary>Report threshold & limits</summary><p>{report.evidence.report_trend}</p></details>}
      </section>
      <section><div className="section-heading"><h3>Signal quality over time</h3><span>Periodicity · %</span></div>
        <Chart values={report.samples.map(s => s.sqi == null ? null : s.sqi * 100)} times={report.samples.map(s => s.t)} label="Signal periodicity over the session" unit="%" domain={[0, 100]} height={150} showScale />
        <div className="axis"><span>0:00</span><span>{clockText(stats.duration)}</span></div>
      </section>
    </div>
    </section>
    <HealthInsights bundle={report.health_insights} />
    <section className="report-section">
      <header className="report-section-heading"><h2>Measurement quality &amp; guidance details</h2><p>Signal quality and observed responses to measurement guidance.</p></header>
      <div className="panel">
      <div className="report-detail-sections">{([["quality", "Measurement quality"], ["interventions", "Guidance during this session"]] as const).map(([key, title]) => <section key={key}>
        <h3>{title}</h3>
        {report.analysis[key].map((item, i) => <div className="statement" key={i}><p>{item.text}</p>
          <details><summary>View supporting evidence</summary>{item.evidence_ids.map(id => <p key={id}>{report.evidence[id]}</p>)}</details>
        </div>)}
      </section>)}</div>
    {report.interventions.length > 0 && <section className="intervention-report"><h3>Guidance & observed outcomes</h3>
      <p>Observed before/after comparisons do not establish causal benefit or heart-rate accuracy.</p>
      {report.interventions.map(item => <div className="intervention-row" key={item.id}><span>{clockText(item.started_at)}{item.evaluated_at != null && <>–{clockText(item.evaluated_at)}</>}</span><div><strong>{item.action}</strong><p>{decisionLabel(item)}</p><p>{item.before_sqi == null || item.after_sqi == null ? "Not enough comparable signal" : `Periodicity: ${percent(item.before_sqi)} → ${percent(item.after_sqi)}. Change: ${Math.round(item.delta! * 100)} percentage points.`}</p><p>Usable windows: {percent(item.before_usable)} → {percent(item.after_usable)}</p></div><span className={`outcome ${item.outcome}`}>{item.outcome}</span></div>)}
    </section>}
    <div className="quality-detail"><span>Face tracking <strong>{percent(stats.tracking_fraction)}</strong></span><span>Mean capture rate <strong>{stats.mean_fps} fps</strong></span><span>Signal coverage <strong>{percent(stats.signal_coverage)}</strong></span></div>
    </div>
    </section>
    {report.capture_diagnostics && <section className="report-section">
      <header className="report-section-heading"><h2>Technical capture details</h2><p>Capture settings and frame delivery recorded during this session.</p></header>
      <div className="panel capture-details">
      <p>{report.capture_diagnostics.width} × {report.capture_diagnostics.height} capture. Camera track reports {report.capture_diagnostics.track_fps?.toFixed(1) ?? "unavailable"} fps.</p>
      <p>Observed video callbacks: {report.capture_diagnostics.callback_fps?.toFixed(1) ?? "—"} fps. Submitted frames: {report.capture_diagnostics.sent_fps?.toFixed(1) ?? "—"} fps. Server-processed capture: {stats.mean_fps} fps.</p>
      <p>{report.capture_diagnostics.frames_acknowledged} / {report.capture_diagnostics.frames_sent} submitted frames acknowledged. Mean / maximum acknowledgement round trip: {report.capture_diagnostics.mean_ack_round_trip_ms?.toFixed(1) ?? "—"} / {report.capture_diagnostics.max_ack_round_trip_ms?.toFixed(1) ?? "—"} ms.</p>
      <p>Mean / maximum sample frame age at receipt: {report.capture_diagnostics.mean_sample_frame_age_ms?.toFixed(1) ?? "—"} / {report.capture_diagnostics.max_sample_frame_age_ms?.toFixed(1) ?? "—"} ms. Maximum sample arrival gap: {report.capture_diagnostics.max_sample_gap_ms?.toFixed(1) ?? "—"} ms.</p>
      <p>Browser observations measure callbacks and delivery, including encoding and server work. Camera settings are reported by the track. These are not model-only throughput or reference-device accuracy measurements. Per-sample server processing time and inference timeline lag are included in the JSON export.</p>
      </div>
    </section>}
    <footer className="report-footer"><p>Signal quality describes the measurement, not your health. Accuracy has not been verified against a reference device.</p><button className="primary" onClick={onNew}>Start a new measurement</button></footer>
  </div>;
}
