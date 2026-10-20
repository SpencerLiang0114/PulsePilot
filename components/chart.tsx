"use client";

import { useId, useState } from "react";

export function Chart({ values, times, label, color = "#168286", height = 110, domain, unit = "", showScale = false, empty = "Your signal will appear here" }: {
  values: (number | null)[]; times?: number[]; label: string; color?: string; height?: number;
  domain?: [number, number]; unit?: string; showScale?: boolean; empty?: string;
}) {
  const id = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);
  const valid = values.filter((v): v is number => v !== null && Number.isFinite(v));
  const low = domain?.[0] ?? (valid.length ? Math.min(...valid) - 0.3 : -1);
  const high = domain?.[1] ?? (valid.length ? Math.max(...valid) + 0.3 : 1);
  const x = (i: number) => times && times.length > 1
    ? 8 + ((times[i] - times[0]) / Math.max(1, times[times.length - 1] - times[0])) * 584
    : 8 + (i / Math.max(1, values.length - 1)) * 584;
  const y = (v: number) => height - 12 - ((v - low) / Math.max(0.1, high - low)) * (height - 24);
  let pen = false;
  const path = values.map((v, i) => {
    if (v === null || !Number.isFinite(v)) { pen = false; return ""; }
    const command = `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
    return command;
  }).join(" ");
  return <div className="chart" style={{ height }} onMouseLeave={() => setHover(null)}>
    <svg viewBox={`0 0 600 ${height}`} preserveAspectRatio="none" role="img" aria-label={label}
      onMouseMove={e => {
        const rect = e.currentTarget.getBoundingClientRect();
        setHover(Math.max(0, Math.min(values.length - 1, Math.round((e.clientX - rect.left) / rect.width * (values.length - 1)))));
      }}>
      <defs><pattern id={id} width="60" height="28" patternUnits="userSpaceOnUse"><path d="M 60 0 L 0 0 0 28" fill="none" stroke="#e6edf0" strokeWidth="1" /></pattern></defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
      {valid.length > 1 && <path d={path} fill="none" stroke={color} strokeWidth="2.2" vectorEffect="non-scaling-stroke" />}
      {hover !== null && values[hover] != null && <>
        <line x1={x(hover)} x2={x(hover)} y1="0" y2={height} stroke="#8c9ca9" strokeDasharray="3 4" />
        <circle cx={x(hover)} cy={y(values[hover]!)} r="3" fill={color} />
      </>}
    </svg>
    {valid.length <= 1 && <div className="chart-empty">{empty}</div>}
    {showScale && <div className="chart-scale" aria-hidden="true"><span>{Math.round(high)}</span><span>{Math.round(low)}</span></div>}
    {hover !== null && values[hover] != null && <div className="chart-tooltip">
      {times ? `${times[hover]?.toFixed(1)}s · ` : ""}{values[hover]?.toFixed(1)} {unit}
    </div>}
  </div>;
}
