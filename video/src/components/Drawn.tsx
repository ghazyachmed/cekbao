// Progressive line-drawing primitives (SVG). Every element is driven by the
// scene time `t` (seconds), which comes from useCurrentFrame() / fps.
import React from "react";
import { C, FONT } from "../theme";
import { fade, prog } from "../anim";

type StrokeProps = {
  d: string; t: number; t0: number; dur?: number; color?: string; w?: number;
  opacity?: number; dashed?: boolean;
};

/** A path that draws itself from start to end. */
export const Stroke: React.FC<StrokeProps> = ({ d, t, t0, dur = 0.9, color = C.line, w = 3, opacity = 1, dashed }) => {
  const p = prog(t, t0, t0 + dur);
  if (p <= 0) return null;
  if (dashed) {
    // Dashed strokes fade in instead of drawing (dash patterns would fight the draw trick).
    return <path d={d} fill="none" stroke={color} strokeWidth={w} strokeDasharray="10 12" strokeLinecap="round" opacity={opacity * p} />;
  }
  return (
    <path d={d} pathLength={1} fill="none" stroke={color} strokeWidth={w} strokeLinecap="round"
      strokeLinejoin="round" strokeDasharray="1 1" strokeDashoffset={1 - p} opacity={opacity} />
  );
};

export const rr = (x: number, y: number, w: number, h: number, r = 18) =>
  `M ${x + r} ${y} H ${x + w - r} A ${r} ${r} 0 0 1 ${x + w} ${y + r} V ${y + h - r} A ${r} ${r} 0 0 1 ${x + w - r} ${y + h} ` +
  `H ${x + r} A ${r} ${r} 0 0 1 ${x} ${y + h - r} V ${y + r} A ${r} ${r} 0 0 1 ${x + r} ${y} Z`;

export const curve = (x1: number, y1: number, x2: number, y2: number, bend = 0.5) => {
  const dx = (x2 - x1) * bend;
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
};

/** Arrow head at (x, y) pointing right, revealed when the connector finishes. */
export const Head: React.FC<{ x: number; y: number; t: number; t0: number; color?: string; dir?: "right" | "down" }> = ({ x, y, t, t0, color = C.line, dir = "right" }) => {
  const o = fade(t, t0, 0.25);
  const d = dir === "right" ? `M ${x - 16} ${y - 10} L ${x} ${y} L ${x - 16} ${y + 10}` : `M ${x - 10} ${y - 16} L ${x} ${y} L ${x + 10} ${y - 16}`;
  return <path d={d} fill="none" stroke={color} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" opacity={o} />;
};

type TxtProps = {
  x: number; y: number; t: number; t0: number; size?: number; weight?: number; color?: string;
  anchor?: "start" | "middle" | "end"; lines: string[]; lh?: number; italic?: boolean; out?: number; spacing?: number;
};

/** Text that fades and rises into place. One <tspan> per line. */
export const Txt: React.FC<TxtProps> = ({ x, y, t, t0, size = 34, weight = 400, color = C.line, anchor = "start", lines, lh = 1.25, italic, out, spacing = 0 }) => {
  const o = fade(t, t0, 0.45, out);
  if (o <= 0) return null;
  const rise = (1 - prog(t, t0, t0 + 0.6)) * 12;
  return (
    <text x={x} y={y + rise} fontFamily={FONT} fontSize={size} fontWeight={weight} fill={color} textAnchor={anchor}
      opacity={o} fontStyle={italic ? "italic" : "normal"} letterSpacing={spacing}>
      {lines.map((l, i) => (
        <tspan key={i} x={x} dy={i === 0 ? 0 : size * lh}>{l}</tspan>
      ))}
    </text>
  );
};

/** A rounded box that draws its outline, with optional fill fading in. */
export const Box: React.FC<{ x: number; y: number; w: number; h: number; t: number; t0: number; color?: string; fill?: string; r?: number; sw?: number; dashed?: boolean; out?: number }> = ({ x, y, w, h, t, t0, color = C.line, fill, r = 18, sw = 3, dashed, out }) => {
  const o = out === undefined ? 1 : 1 - prog(t, out - 0.4, out);
  return (
    <g opacity={o}>
      {fill ? <path d={rr(x, y, w, h, r)} fill={fill} opacity={fade(t, t0 + 0.3, 0.5)} /> : null}
      <Stroke d={rr(x, y, w, h, r)} t={t} t0={t0} color={color} w={sw} dashed={dashed} />
    </g>
  );
};

/** Full-frame SVG canvas for diagram scenes. */
export const Canvas: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <svg viewBox="0 0 1920 1080" width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>{children}</svg>
);
