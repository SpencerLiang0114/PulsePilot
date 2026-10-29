"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Sample } from "@/lib/types";

export function PulseWaveform({ sample, active, playbackRate = 1, label }: {
  sample: Sample | null; active: boolean; playbackRate?: number; label: string;
}) {
  const clip = useId().replace(/:/g, "");
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);
  const [clock, setClock] = useState(0);
  const [pointer, setPointer] = useState<number | null>(null);
  const sampleTime = sample?.t ?? 0;
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)));
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const received = performance.now();
    const animate = active && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    const tick = () => {
      const elapsed = animate ? Math.min((performance.now() - received) / 1000, .75) : 0;
      setClock(sampleTime + elapsed * playbackRate);
      if (animate && elapsed < .75) frame = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(frame);
  }, [sampleTime, active, playbackRate]);

  const values = sample?.waveform ?? [];
  const times = sample?.waveform_times ?? [];
  const points = values.flatMap((value, i) => Number.isFinite(value) && Number.isFinite(times[i])
    ? [{ t: times[i], value }] : []);
  const end = Math.max(8, sampleTime, clock), start = end - 8;
  const left = 36, right = width - 10, top = 20, bottom = 108;
  const x = (t: number) => left + (t - start) / 8 * (right - left);
  const limit = Math.max(2, Math.ceil(Math.max(0, ...points.map(p => Math.abs(p.value)))));
  const y = (v: number) => top + (limit - v) / (limit * 2) * (bottom - top);
  const path = points.map((p, i) => `${i && p.t - points[i - 1].t < .1 ? "L" : "M"}${x(p.t).toFixed(2)},${y(p.value).toFixed(2)}`).join(" ");
  const peaks: typeof points = [];
  points.forEach((p, i) => {
    if (i && i < points.length - 1 && p.value > .35 && p.value > points[i - 1].value
      && p.value >= points[i + 1].value && p.t - (peaks.at(-1)?.t ?? -Infinity) > .35) peaks.push(p);
  });
  const tickStep = width < 440 ? 2 : 1;
  const ticks = Array.from({ length: 9 }, (_, i) => Math.ceil(start / tickStep) * tickStep + i * tickStep).filter(t => t <= end);
  const visible = points.filter(p => p.t >= start && p.t <= end);
  const selected = pointer === null ? null : visible.reduce<(typeof points)[number] | null>((best, p) =>
    !best || Math.abs(x(p.t) - pointer) < Math.abs(x(best.t) - pointer) ? p : best, null);
  return <div ref={container} className="pulse-waveform" data-window-start={start.toFixed(3)} data-window-end={end.toFixed(3)}
    onPointerLeave={() => setPointer(null)}>
    <svg viewBox={`0 0 ${width} 132`} role="img" aria-label={label}
      onPointerMove={e => setPointer(e.clientX - e.currentTarget.getBoundingClientRect().left)}>
      <defs><clipPath id={clip}><rect x={left} y={top} width={right - left} height={bottom - top} /></clipPath></defs>
      <text x={left} y="11" className="wave-label">BVP · normalized</text>
      <text x={right} y="11" textAnchor="end" className="wave-label">8 s window</text>
      {[-limit, -limit / 2, 0, limit / 2, limit].map(v => <g key={v}>
        <line x1={left} x2={right} y1={y(v)} y2={y(v)} className={v === 0 ? "wave-zero" : "wave-grid"} />
        <text x={left - 6} y={y(v) + 3} textAnchor="end" className="wave-label">{v.toFixed(1)}</text>
      </g>)}
      {ticks.map(t => <g key={t}>
        <line x1={x(t)} x2={x(t)} y1={top} y2={bottom} className="wave-grid" />
        <text x={x(t)} y="124" textAnchor="middle" className="wave-label">{t}s</text>
      </g>)}
      <g clipPath={`url(#${clip})`}>
        <path className="wave-trace" d={path} fill="none" stroke="currentColor" strokeWidth="1.8" />
        {peaks.map(p => <circle key={p.t} cx={x(p.t)} cy={y(p.value)} r="2.5" className="wave-peak" />)}
        {points.length > 0 && <line x1={x(points.at(-1)!.t)} x2={x(points.at(-1)!.t)} y1={top} y2={bottom} className="wave-cursor" />}
        {selected && <><line x1={x(selected.t)} x2={x(selected.t)} y1={top} y2={bottom} className="wave-cursor" />
          <circle cx={x(selected.t)} cy={y(selected.value)} r="3" fill="currentColor" /></>}
      </g>
    </svg>
    {visible.length < 2 && <div className="chart-empty">Waiting for fresh pulse samples</div>}
    {selected && <div className="chart-tooltip">{selected.t.toFixed(2)} s · {selected.value.toFixed(2)} normalized BVP</div>}
  </div>;
}
