"use client";

import { Activity, ArrowLeft, Clock3, Download, Heart, Printer, CircleCheck, FlaskConical, Signal, Waves } from "lucide-react";
import { Chart } from "./chart";
import { Analysis, HealthInsightBundle, clockText, decisionLabel, percent, Report as ReportData } from "@/lib/types";

function PulseVariabilityResults({ report }: { report: ReportData }) {
  const result = report.pulse_variability;
  const available = report.mode !== "simulation" && result?.status === "available";
  return <section aria-label="Pulse variability" className="report-section">
    <header className="report-section-heading"><h2>Pulse variability</h2>
      <p>Beat-to-beat timing from your BVP waveform · experimental camera-based HRV estimate</p></header>
    <div className="panel variability-panel">
      <div className="report-stats variability-stats">
        <div><span>Successive variation · RMSSD</span><strong>{available ? result.rmssd_ms : "—"} <small>ms</small></strong></div>
        <div><span>Interval spread · SDNN</span><strong>{available ? result.sdnn_ms : "—"} <small>ms</small></strong></div>
        <div><span>Continuous segment</span><strong>{result ? clockText(result.duration) : "—"}</strong></div>
        <div><span>Pulse intervals</span><strong>{result?.interval_count ?? "—"}</strong></div>
      </div>
      <h3>{available ? "What your pulse timing tells you" : "Pulse variability is unavailable"}</h3>
      <p>{report.mode === "simulation" ? "Synthetic data cannot measure your HRV. Start a camera measurement to collect your own pulse waveform." :
        available ? "Your heart does not beat at perfectly equal intervals. RMSSD describes differences between successive pulse intervals; SDNN describes their overall spread in this segment. These values describe pulse timing, not a health grade." :
        result?.reason ?? "The measurement service did not include beat-to-beat analysis in this report. It may be running an earlier version. Restart the backend with the latest code, then record again; average heart-rate readings cannot reconstruct HRV."}</p>
      {available && <>
        <div className="section-heading"><h3><Waves size={18} aria-hidden="true" />Pulse intervals over time</h3><span>Interval · ms</span></div>
        <Chart values={result.intervals_ms} times={result.interval_times} label="Pulse intervals in the analyzed continuous segment" unit="ms" height={150} showScale />
        <div className="axis"><span>{clockText(result.interval_times[0] ?? 0)}</span><span>{clockText(result.interval_times.at(-1) ?? 0)}</span></div>
        <p>For a useful personal baseline, compare recordings of similar length, taken at a similar time and in the same resting position. A single value cannot establish stress, recovery, fitness, or disease.</p>
      </>}
      <details className="trend-note"><summary>How this estimate is calculated</summary>
        <p>Pulse peaks are detected in timestamped BVP windows that passed the live measurement checks. Overlapping windows are counted once. Gaps and rejected intervals split segments; only the longest continuous segment is used, with at least 30 seconds and 30 pulse intervals. Intervals are included in the JSON export.</p>
        <p>This is pulse-rate variability (PRV), not ECG-measured HRV. Camera timing and pulse-wave effects can change the result. Short recordings are exploratory and are not interchangeable with standard five-minute recordings. No synchronized ECG validation has been performed.</p>
        {result && <p>{result.rejected_intervals} intervals rejected by timing checks. Rejection does not identify abnormal heartbeats.</p>}
        <p><a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC8704576/" target="_blank" rel="noreferrer">Research on camera-based pulse variability</a> · <a href="https://www.escardio.org/static-file/Escardio/Guidelines/Scientific-Statements/guidelines-Heart-Rate-Variability-FT-1996.pdf" target="_blank" rel="noreferrer">HRV measurement standards</a></p>
      </details>
    </div>
  </section>;
}

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
    <div className="panel health-insight-panel">
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
      <div className="completion-label"><CircleCheck size={18} /> Measurement complete</div>
      <h1>Session report</h1>
      <p>{new Date(report.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</p>
      <div className="report-session-meta"><span><Clock3 size={14} aria-hidden="true" />{clockText(stats.duration)} session</span><span><Activity size={14} aria-hidden="true" />{report.mode === "camera" ? "Live camera" : report.mode === "recording" ? "Video recording" : "Simulation"}</span></div></div>
      <div className="report-emblem" aria-hidden="true"><Activity size={30} strokeWidth={1.5} /></div>
    </header>
    <section aria-label="Measurement overview" className="report-overview panel">
      <div className={`report-pulse-summary${stats.mean_bpm == null ? " is-unavailable" : ""}`}>
        <h2>Average estimated heart rate</h2>
        <div className="report-pulse-dial">
          <svg viewBox="0 0 280 280" aria-hidden="true"><circle className="report-pulse-ticks" cx="140" cy="140" r="123" /><circle className="report-pulse-inner" cx="140" cy="140" r="101" /></svg>
          <div className="report-main-number"><Heart size={22} aria-hidden="true" /><div>{stats.mean_bpm ?? "—"}</div><span>BPM</span></div>
        </div>
        <p>{stats.mean_bpm == null ? "Insufficient usable signal" : "From accepted measurement windows"}</p>
      </div>
      <div className="report-overview-details">
        <div className="report-stats">
          <div><span><Heart size={17} aria-hidden="true" />Median heart rate</span><strong>{stats.median_bpm ?? "—"} <small>BPM</small></strong><p>Middle accepted reading</p></div>
          <div className="report-range"><span><Activity size={17} aria-hidden="true" />Observed range</span><strong>{stats.min_bpm == null ? "—" : `${stats.min_bpm}–${stats.max_bpm}`} <small>BPM</small></strong><p>Accepted session estimates</p></div>
          <div><span><Signal size={17} aria-hidden="true" />Accepted readings</span><strong>{percent(stats.usable_fraction)}</strong><p>Passed measurement checks</p></div>
          <div><span><Clock3 size={17} aria-hidden="true" />First stable signal</span><strong>{stats.stable_at == null ? "—" : clockText(stats.stable_at)}</strong><p>Time from session start</p></div>
        </div>
        <p className="report-overview-note">Signal quality describes the measurement. It is not a health score.</p>
      </div>
    </section>
    <PulseVariabilityResults report={report} />
    <HealthInsights bundle={report.health_insights} />
    <section className="report-section">
    <header className="report-section-heading"><h2>Recording summary &amp; next measurement</h2><p>
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
