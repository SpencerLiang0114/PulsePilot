"use client";

import { useId, useState } from "react";

export function Chart({ values, preliminary, times, label, color = "var(--accent)", height = 110, domain, unit = "", showScale = false, empty = "Your signal will appear here" }: {
  values: (number | null)[]; times?: number[]; label: string; color?: string; height?: number;
  preliminary?: (number | null)[];
  domain?: [number, number]; unit?: string; showScale?: boolean; empty?: string;
}) {
  const id = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);
  const valid = [...values, ...(preliminary ?? [])].filter((v): v is number => v !== null && Number.isFinite(v));
  const low = domain?.[0] ?? (valid.length ? Math.min(...valid) - 0.3 : -1);
  const high = domain?.[1] ?? (valid.length ? Math.max(...valid) + 0.3 : 1);
  const x = (i: number) => times && times.length > 1
    ? 8 + ((times[i] - times[0]) / Math.max(1, times[times.length - 1] - times[0])) * 584
    : 8 + (i / Math.max(1, values.length - 1)) * 584;
  const y = (v: number) => height - 12 - ((v - low) / Math.max(0.1, high - low)) * (height - 24);
  const series = [{ values, color, name: preliminary ? "Accepted" : label, dashed: false },
    ...(preliminary ? [{ values: preliminary, color: "#a36614", name: "Preliminary", dashed: true }] : [])];
  const hoverValue = hover == null ? null : values[hover] ?? preliminary?.[hover];
  return <div className="chart" style={{ height }} onMouseLeave={() => setHover(null)}>
    <svg viewBox={`0 0 600 ${height}`} preserveAspectRatio="none" role="img" aria-label={label}
      onMouseMove={e => {
        const rect = e.currentTarget.getBoundingClientRect();
        const position = (e.clientX - rect.left) / rect.width * 600;
        setHover(values.length ? values.reduce<number>((nearest, _, i) =>
          Math.abs(x(i) - position) < Math.abs(x(nearest) - position) ? i : nearest, 0) : null);
      }}>
      <defs><pattern id={id} width="60" height="28" patternUnits="userSpaceOnUse"><path d="M 60 0 L 0 0 0 28" fill="none" stroke="var(--line)" strokeWidth="1" /></pattern></defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
      {series.map(series => {
        let pen = false;
        const path = series.values.map((v, i) => {
          if (v === null || !Number.isFinite(v)) { pen = false; return ""; }
          const contiguous = pen && (!times || times[i] - times[i - 1] <= 1.5);
          pen = true;
          return `${contiguous ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
        }).join(" ");
        return <g key={series.name} data-series={series.name}>
          <path d={path} fill="none" stroke={series.color} strokeWidth="2.2" strokeDasharray={series.dashed ? "4 4" : undefined} vectorEffect="non-scaling-stroke" />
          {series.values.map((v, i) => v != null && Number.isFinite(v) ?
            <circle key={i} cx={x(i)} cy={y(v)} r="2.5" fill={series.dashed ? "white" : series.color} stroke={series.color}>
              <title>{series.name}: {v.toFixed(1)} {unit}{times ? ` at ${times[i].toFixed(1)}s` : ""}</title>
            </circle> : null)}
        </g>;
      })}
      {hover !== null && hoverValue != null && <>
        <line x1={x(hover)} x2={x(hover)} y1="0" y2={height} stroke="#8c9ca9" strokeDasharray="3 4" />
        <circle cx={x(hover)} cy={y(hoverValue)} r="3" fill={values[hover] != null ? color : "#a36614"} />
      </>}
    </svg>
    {valid.length === 0 && <div className="chart-empty">{empty}</div>}
    {showScale && <div className="chart-scale" aria-hidden="true"><span>{Math.round(high)}</span><span>{Math.round(low)}</span></div>}
    {hover !== null && hoverValue != null && <div className="chart-tooltip">
      {times ? `${times[hover]?.toFixed(1)}s · ` : ""}{hoverValue.toFixed(1)} {unit}{values[hover] == null ? " · Preliminary" : ""}
    </div>}
  </div>;
}
