// Real CEKBAO capture viewer. Shows ONLY real screenshots of the running app.
// Motion between shots is camera framing (pan/zoom) and crossfades between real
// states. The cursor is an overlay placed at the recorded click coordinates.
import React from "react";
import { Img, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import { Box, center, imgSize } from "../captures";
import { C, FONT } from "../theme";
import { fade, lerp, prog } from "../anim";
import { rr, Stroke } from "./Drawn";

export const WIN = { x: 120, y: 100, w: 1680, bar: 46, h: 746 };
const VX = WIN.x;
const VY = WIN.y + WIN.bar;
const VW = WIN.w;
const VH = WIN.h - WIN.bar; // 700

export type Click = { x: number; y: number; at: number };
export type Mark = { box: Box; color: string; label?: string; at: number; until?: number; labelBelow?: boolean };
export type Shot = { img: string; t0: number; t1: number; s: number; cx: number; cy: number; clicks?: Click[]; marks?: Mark[] };
type Cam = { img: string; s: number; cx: number; cy: number };

const clampCam = (c: Cam): Cam => {
  const { w, h } = imgSize(c.img);
  const halfW = VW / 2 / c.s;
  const halfH = VH / 2 / c.s;
  const cx = w * c.s <= VW ? w / 2 : Math.min(Math.max(c.cx, halfW), w - halfW);
  const cy = h * c.s <= VH ? h / 2 : Math.min(Math.max(c.cy, halfH), h - halfH);
  return { ...c, cx, cy };
};

const toScreen = (cam: Cam, x: number, y: number) => ({ x: VX + VW / 2 + (x - cam.cx) * cam.s, y: VY + VH / 2 + (y - cam.cy) * cam.s });

const Layer: React.FC<{ cam: Cam; opacity: number }> = ({ cam, opacity }) => {
  const { w, h } = imgSize(cam.img);
  const left = VW / 2 - cam.cx * cam.s;
  const top = VH / 2 - cam.cy * cam.s;
  return (
    <Img src={staticFile(`captures/${cam.img}.png`)}
      style={{ position: "absolute", left, top, width: w * cam.s, height: h * cam.s, opacity, maxWidth: "none" }} />
  );
};

const Cursor: React.FC<{ x: number; y: number; opacity: number }> = ({ x, y, opacity }) => (
  <svg width={44} height={52} viewBox="0 0 22 26" style={{ position: "absolute", left: x - 3, top: y - 2, opacity, filter: "drop-shadow(0 2px 3px rgba(0,0,0,.6))" }}>
    <path d="M1 1 L1 20 L6 15 L9.5 23 L13 21.5 L9.5 14 L16.5 14 Z" fill="#FFFFFF" stroke="#070B10" strokeWidth={1.4} strokeLinejoin="round" />
  </svg>
);

export const CaptureWindow: React.FC<{ shots: Shot[]; url?: string; label?: string; children?: React.ReactNode }> = ({ shots, url = "127.0.0.1:8765", label = "Real app capture · local sandbox · synthetic data", children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  let k = shots.findIndex((s) => t >= s.t0 && t < s.t1);
  if (k === -1) k = t < shots[0].t0 ? 0 : shots.length - 1;
  const shot = shots[k];
  const prev = k > 0 ? shots[k - 1] : null;
  const target = clampCam({ img: shot.img, s: shot.s, cx: shot.cx, cy: shot.cy });

  let cam = target;
  const layers: { cam: Cam; opacity: number }[] = [];
  if (prev && prev.img === shot.img) {
    const from = clampCam({ img: prev.img, s: prev.s, cx: prev.cx, cy: prev.cy });
    const p = prog(t, shot.t0, shot.t0 + 1.1);
    cam = clampCam({ img: shot.img, s: lerp(from.s, target.s, p), cx: lerp(from.cx, target.cx, p), cy: lerp(from.cy, target.cy, p) });
    layers.push({ cam, opacity: 1 });
  } else if (prev) {
    const p = prog(t, shot.t0, shot.t0 + 0.4);
    layers.push({ cam: clampCam({ img: prev.img, s: prev.s, cx: prev.cx, cy: prev.cy }), opacity: 1 });
    layers.push({ cam: target, opacity: p });
  } else {
    layers.push({ cam: target, opacity: 1 });
  }

  // Cursor: travels to each recorded click target of the current shot.
  let cursor: { x: number; y: number; o: number } | null = null;
  const clicks = shot.clicks ?? [];
  if (clicks.length) {
    let px = VX + VW * 0.72;
    let py = VY + VH * 0.72;
    for (const c of clicks) {
      const sc = toScreen(cam, c.x, c.y);
      if (t < c.at) {
        const p = prog(t, c.at - 1.0, c.at - 0.12);
        cursor = { x: lerp(px, sc.x, p), y: lerp(py, sc.y, p), o: fade(t, shot.t0, 0.3) };
        break;
      }
      px = sc.x;
      py = sc.y;
      cursor = { x: sc.x, y: sc.y, o: 1 - prog(t, c.at + 0.25, c.at + 0.55) };
    }
  }

  const dim = 1;
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {/* window */}
      <div style={{ position: "absolute", left: WIN.x, top: WIN.y, width: WIN.w, height: WIN.h, borderRadius: 16, border: `1.5px solid ${C.faint}`, overflow: "hidden", background: "#0A1622" }}>
        <div style={{ position: "absolute", left: 0, top: 0, right: 0, height: WIN.bar, background: "#0E1822", borderBottom: `1px solid ${C.faint}`, display: "flex", alignItems: "center", gap: 10, paddingLeft: 18 }}>
          {[C.faint, C.faint, C.faint].map((c, i) => <div key={i} style={{ width: 12, height: 12, borderRadius: 6, background: c }} />)}
          <div style={{ marginLeft: 18, fontFamily: FONT, fontSize: 22, color: C.dim, background: "#070B10", borderRadius: 8, padding: "4px 14px" }}>{url}</div>
          <div style={{ marginLeft: "auto", marginRight: 18, fontFamily: FONT, fontSize: 22, fontWeight: 700, letterSpacing: 1.5, color: C.teal, textTransform: "uppercase" }}>{label}</div>
        </div>
        <div style={{ position: "absolute", left: 0, top: WIN.bar, width: VW, height: VH, overflow: "hidden", opacity: dim }}>
          {layers.map((l, i) => <Layer key={i} cam={l.cam} opacity={l.opacity} />)}
        </div>
      </div>
      {/* annotation layer (marks are drawn over real UI regions, labelled as annotations) */}
      <svg viewBox="0 0 1920 1080" width={1920} height={1080} style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        <defs><clipPath id="vp"><rect x={VX} y={VY} width={VW} height={VH} /></clipPath></defs>
        <g clipPath="url(#vp)">
          {(shot.marks ?? []).map((m, i) => {
            const a = toScreen(cam, m.box.x - 10, m.box.y - 10);
            const b = toScreen(cam, m.box.x + m.box.w + 10, m.box.y + m.box.h + 10);
            const o = m.until ? 1 - prog(t, m.until - 0.3, m.until) : 1;
            return <g key={i} opacity={o}><Stroke d={rr(a.x, a.y, b.x - a.x, b.y - a.y, 14)} t={t} t0={m.at} dur={0.7} color={m.color} w={4} /></g>;
          })}
        </g>
      </svg>
      {(shot.marks ?? []).filter((m) => m.label).map((m, i) => {
        const a = toScreen(cam, m.box.x - 10, m.box.y - 10);
        const b = toScreen(cam, m.box.x + m.box.w + 10, m.box.y + m.box.h + 10);
        const o = fade(t, m.at + 0.4, 0.4, m.until);
        const top = m.labelBelow ? Math.min(b.y + 12, VY + VH - 60) : Math.max(a.y - 58, VY + 8);
        return (
          <div key={i} style={{ position: "absolute", left: Math.max(a.x, VX + 12), top, opacity: o, fontFamily: FONT, fontSize: 28, fontWeight: 800, color: "#070B10", background: m.color, borderRadius: 10, padding: "6px 16px" }}>
            {m.label}
          </div>
        );
      })}
      {cursor && cursor.o > 0 ? <Cursor x={cursor.x} y={cursor.y} opacity={cursor.o} /> : null}
      {clicks.map((c, i) => {
        const sc = toScreen(cam, c.x, c.y);
        const p = prog(t, c.at, c.at + 0.45);
        return p > 0 && p < 1 ? (
          <div key={i} style={{ position: "absolute", left: sc.x - 36 * p, top: sc.y - 36 * p, width: 72 * p, height: 72 * p, borderRadius: "50%", border: `3px solid ${C.line}`, opacity: 1 - p }} />
        ) : null;
      })}
      {shots.flatMap((s) => s.clicks ?? []).map((c, i) => (
        <Sequence key={`sfx${i}`} from={Math.round(c.at * fps)} durationInFrames={12} layout="none">
          <Audio src={staticFile("audio/sfx_click.wav")} volume={0.35} />
        </Sequence>
      ))}
      {children}
    </div>
  );
};

export const at = (b: Box, t: number): Click => ({ ...center(b), at: t });
