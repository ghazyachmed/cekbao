import { useCurrentFrame, useVideoConfig } from "remotion";
import { prog } from "../motion.ts";
import { C, FONT, L, V } from "../theme.ts";

// Header row inside the safe area: scene label on the left, persistent truth labels on the right.
export const Header: React.FC<{ left: string; preview: boolean; recording?: boolean; accent?: string }> =
  ({ left, preview, recording = false, accent = V.teal }) => {
    const frame = useCurrentFrame();
    return (
      <div style={{ position: "absolute", top: L.headerTop, left: L.safeX, right: L.safeX, height: 44, display: "flex",
                    alignItems: "center", gap: 14, fontFamily: FONT, opacity: prog(frame, 0, 10),
                    translate: `${(1 - prog(frame, 0, 14)) * -24}px 0px` }}>
        <span style={{ width: 14, height: 14, borderRadius: 99, background: accent, boxShadow: `0 0 18px ${accent}` }} />
        <span style={{ color: C.text, fontWeight: 700, fontSize: 30 }}>{left}</span>
        <span style={{ flex: 1 }} />
        {recording ? <Badge color={V.teal}>Real app recording</Badge> : null}
        <Badge color={V.amber} dashed>Synthetic data</Badge>
        {preview ? <Badge color={V.coral}>PREVIEW: model not called</Badge> : null}
      </div>
    );
  };

export const Badge: React.FC<{ color: string; dashed?: boolean; children: React.ReactNode }> = ({ color, dashed, children }) => (
  <span style={{ border: `2px ${dashed ? "dashed" : "solid"} ${color}`, color, borderRadius: 999, padding: "2px 16px",
                 fontWeight: 700, fontSize: 26, whiteSpace: "nowrap", background: "rgba(6,11,24,0.6)" }}>{children}</span>
);

export const Card: React.FC<{ style?: React.CSSProperties; children: React.ReactNode }> = ({ style, children }) => (
  <div style={{ background: C.card, color: C.cardInk, borderRadius: 18, padding: 36, fontFamily: FONT, ...style }}>
    {children}
  </div>
);

/** CEKBAO mark: the app's "C" tile with a gradient, plus the wordmark. */
export const Logo: React.FC<{ size?: number }> = ({ size = 72 }) => (
  <div style={{ display: "flex", alignItems: "center", gap: size * 0.3, fontFamily: FONT }}>
    <div style={{ width: size, height: size, borderRadius: size * 0.24, display: "grid", placeItems: "center",
                  background: `linear-gradient(135deg, ${V.teal}, ${V.blue})`, color: V.ink, fontWeight: 900,
                  fontSize: size * 0.62, boxShadow: `0 0 ${size * 0.6}px ${V.teal}66` }}>C</div>
    <div style={{ color: "#fff", fontWeight: 900, fontSize: size * 0.78, letterSpacing: "0.02em" }}>CEKBAO</div>
  </div>
);

/** Thin progress line across the top edge, coloured by the current scene. */
export const Progress: React.FC<{ color: string }> = ({ color }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <div style={{ position: "absolute", left: 0, top: 0, height: 6, width: `${(frame / durationInFrames) * 100}%`,
                  background: `linear-gradient(90deg, ${V.teal}, ${color})`, boxShadow: `0 0 12px ${color}` }} />
  );
};
