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
    heatmap.values.forEach((value, i) => {
      pixels.data[i * 4] = 255;
      pixels.data[i * 4 + 1] = value;
      pixels.data[i * 4 + 2] = 0;
      pixels.data[i * 4 + 3] = 70 + Math.round(value / 255 * 95);
    });
    context.putImageData(pixels, 0, 0);
  }, [heatmap]);
  const [x1, y1, x2, y2] = heatmap.bbox;
  return <svg className={`face-overlay face-heatmap ${mirrored ? "mirrored" : ""}`}
    viewBox={`0 0 ${captureSize.width} ${captureSize.height}`} preserveAspectRatio="xMidYMid meet"
    role="img" aria-label="Face temporal feature activity heatmap">
    <foreignObject x={x1 * captureSize.width} y={y1 * captureSize.height}
      width={(x2 - x1) * captureSize.width} height={(y2 - y1) * captureSize.height}>
      <canvas ref={canvasRef} width={heatmap.width} height={heatmap.height} />
    </foreignObject>
  </svg>;
}
