"use client";

import { useEffect, useRef } from "react";
import type { FaceHeatmap as Heatmap } from "@/lib/types";

export function FaceHeatmap({ heatmap, captureSize, mirrored }: {
  heatmap: Heatmap; captureSize: { width: number; height: number }; mirrored: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const pixels = context.createImageData(heatmap.width, heatmap.height);
    const pulse = heatmap.pulse ?? .5;
    const gain = 1 + pulse * .25;
    const stops = [[0, 0, 0, 0], [.15, 180, 0, 0], [.4, 255, 20, 0], [.65, 255, 100, 0], [.8, 255, 210, 0], [1, 255, 230, 30]];
    heatmap.values.forEach((value, i) => {
      const intensity = Math.max(0, Math.min(1, value / 255));
      const upper = stops.findIndex((stop, j) => j > 0 && intensity <= stop[0]);
      const from = stops[upper - 1], to = stops[upper];
      const blend = (intensity - from[0]) / (to[0] - from[0]);
      for (let channel = 0; channel < 3; channel++) {
        pixels.data[i * 4 + channel] = Math.min(255, Math.round((from[channel + 1] + blend * (to[channel + 1] - from[channel + 1])) * gain));
      }
      pixels.data[i * 4 + 3] = intensity < .15 ? 0 : Math.round(255 * Math.pow((intensity - .15) / .85, .35));
    });
    context.putImageData(pixels, 0, 0);
    // The demo adds pulse-driven highlights at approximate forehead, cheeks, and nose positions.
    const glow = Math.max(0, (pulse - .2) / .8) * .6;
    if (glow > 0) {
      const regions = [[.5, .18, .25, .12, 0], [.28, .52, .15, .12, -.3], [.72, .52, .15, .12, .3], [.5, .42, .06, .08, 0]];
      for (const [x, y, rx, ry, rotation] of regions) {
        context.save();
        context.translate(x * heatmap.width, y * heatmap.height);
        context.rotate(rotation);
        context.scale(rx * heatmap.width, ry * heatmap.height);
        const gradient = context.createRadialGradient(0, 0, 0, 0, 0, 2.5);
        gradient.addColorStop(0, `rgba(255,190,115,${glow * .95})`);
        gradient.addColorStop(.3, `rgba(255,110,45,${glow * .75})`);
        gradient.addColorStop(.6, `rgba(220,60,25,${glow * .35})`);
        gradient.addColorStop(1, "rgba(120,30,10,0)");
        context.fillStyle = gradient;
        context.fillRect(-2.5, -2.5, 5, 5);
        context.restore();
      }
    }
  }, [heatmap]);
  const [x1, y1, x2, y2] = heatmap.bbox;
  return <svg className={`face-overlay face-heatmap ${mirrored ? "mirrored" : ""}`}
    viewBox={`0 0 ${captureSize.width} ${captureSize.height}`} preserveAspectRatio="xMidYMid meet"
    role="img" aria-label="FacePhys attention heatmap">
    <foreignObject x={x1 * captureSize.width} y={y1 * captureSize.height}
      width={(x2 - x1) * captureSize.width} height={(y2 - y1) * captureSize.height}>
      <canvas ref={canvasRef} width={heatmap.width} height={heatmap.height} />
    </foreignObject>
  </svg>;
}
