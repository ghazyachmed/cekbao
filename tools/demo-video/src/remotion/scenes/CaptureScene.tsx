import { Video } from "@remotion/media";
import { Freeze, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { Click, PlannedScene, Segment } from "../types.ts";
import { Header } from "../components/Chrome.tsx";
import { pop, prog } from "../motion.ts";
import { FONT, L, TONE, V } from "../theme.ts";

// One recorded scenario. Each segment plays the real recording, then holds its last frame while narration
// finishes, with a slow push-in so held frames keep moving. A zoom panel pops out with a sharp crop of the
// element under discussion, and a callout chip names the step. The page itself is never modified.
export const CaptureScene: React.FC<{ scene: PlannedScene; preview: boolean; viewport: { width: number; height: number };
                                      accent: [string, string] }> = ({ scene, preview, viewport, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = L.frameW / viewport.width;
  const enter = pop(frame, 0, fps, 16);
  return (
    <>
      <Header left={`Scenario ${scene.code}: ${scene.title}`} preview={preview} recording accent={accent[0]} />
      <div style={{ position: "absolute", left: L.frameX, top: L.frameY, width: L.frameW, height: L.frameH,
                    borderRadius: 14, overflow: "hidden", background: "#f4f6f8",
                    boxShadow: `0 0 0 3px ${accent[0]}, 0 0 70px ${accent[0]}55, 0 30px 80px rgba(0,0,0,.55)`,
                    scale: String(interpolate(enter, [0, 1], [0.92, 1])), translate: `0px ${(1 - enter) * 40}px`,
                    opacity: prog(frame, 0, 8) }}>
        {scene.segments.map((s, i) => <SegmentView key={i} s={s} viewport={viewport} scale={scale} />)}
      </div>
      {scene.segments.map((s, i) => s.callout ? (
        <Sequence key={`c${i}`} from={s.from} durationInFrames={s.callout.frames} name={`${s.label} (callout)`}>
          <CalloutChip text={s.callout.text} tone={s.callout.tone} total={s.callout.frames} />
        </Sequence>
      ) : null)}
    </>
  );
};

const SegmentView: React.FC<{ s: Segment; viewport: { width: number; height: number }; scale: number }> = ({ s, viewport, scale }) => {
  const total = s.playFrames + s.freezeFrames;
  const video = (
    <Video src={staticFile(s.video)} trimBefore={s.startFrom} muted
           style={{ width: viewport.width, height: viewport.height, scale: String(scale), transformOrigin: "0 0" }} />
  );
  return (
    <>
      <Sequence from={s.from} durationInFrames={s.playFrames} name={`${s.label} (play)`}>
        <Push offset={0} total={total}>
          {video}
          {s.clicks.map((c, i) => <Cursor key={i} c={c} scale={scale} />)}
        </Push>
      </Sequence>
      {s.freezeFrames > 0 ? (
        <Sequence from={s.from + s.playFrames} durationInFrames={s.freezeFrames} name={`${s.label} (hold)`}>
          <Push offset={s.playFrames} total={total}>
            <Freeze frame={Math.max(0, s.playFrames - 1)}>{video}</Freeze>
          </Push>
        </Sequence>
      ) : null}
      {s.inset ? (
        <Sequence from={s.from + s.inset.delay} durationInFrames={total - s.inset.delay} name={`${s.label} (zoom)`}>
          <Zoom src={s.inset.src} w={s.inset.width} h={s.inset.height} color={TONE[s.callout?.tone ?? "info"].color} />
        </Sequence>
      ) : null}
    </>
  );
};

/** Slow push-in across a whole segment (play and hold share one continuous scale). */
const Push: React.FC<{ offset: number; total: number; children: React.ReactNode }> = ({ offset, total, children }) => {
  const frame = useCurrentFrame() + offset;
  return (
    <div style={{ position: "absolute", inset: 0, transformOrigin: "50% 40%",
                  scale: String(interpolate(frame, [0, Math.max(1, total)], [1, 1.035], { extrapolateRight: "clamp" })) }}>
      {children}
    </div>
  );
};

// Pointer drawn by the editor at the recorded click position (the app page itself was never modified).
const Cursor: React.FC<{ c: Click; scale: number }> = ({ c, scale }) => {
  const frame = useCurrentFrame();
  const appear = c.frame - 14;
  if (frame < appear || frame > c.frame + 24) return null;
  const ring = (delay: number) => (
    <div style={{ position: "absolute", left: -30, top: -30, width: 60, height: 60, borderRadius: 999,
                  border: `4px solid ${V.pink}`,
                  opacity: interpolate(frame, [c.frame + delay, c.frame + delay + 18], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
                  scale: String(interpolate(frame, [c.frame + delay, c.frame + delay + 18], [0.5, 1.5], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })) }} />
  );
  return (
    <div style={{ position: "absolute", left: c.x * scale, top: c.y * scale, width: 0, height: 0 }}>
      {ring(0)}{ring(6)}
      <svg width="34" height="34" viewBox="0 0 24 24" style={{ position: "absolute", left: 0, top: 0 }}>
        <path d="M5 3L19 12L12 13L9 20L5 3Z" fill="#ffffff" stroke="#0b1b2b" strokeWidth="1.6" strokeLinejoin="round" />
      </svg>
    </div>
  );
};

const Zoom: React.FC<{ src: string; w: number; h: number; color: string }> = ({ src, w, h, color }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const k = Math.min(1180 / w, 560 / h, 2.0);          // CSS px of the app -> frame px
  const width = Math.round(w * k), height = Math.round(h * k);
  const p = pop(frame, 0, fps, 11);
  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                  background: `rgba(6, 11, 24, ${interpolate(frame, [0, 8], [0, 0.5], { extrapolateRight: "clamp" })})` }}>
      <div style={{ opacity: prog(frame, 0, 6), scale: String(interpolate(p, [0, 1], [0.7, 1])),
                    rotate: `${(1 - p) * -3}deg`, background: "#ffffff", borderRadius: 18, padding: 18,
                    border: `5px solid ${color}`, boxShadow: `0 0 0 10px ${color}33, 0 0 80px ${color}66, 0 24px 60px rgba(0,0,0,.5)` }}>
        <div style={{ display: "inline-block", fontFamily: FONT, fontSize: 24, fontWeight: 800, color: V.ink, marginBottom: 12,
                      background: color, borderRadius: 999, padding: "2px 14px" }}>
          Zoomed from the app
        </div>
        <Img src={staticFile(src)} style={{ width, height, display: "block" }} />
      </div>
    </div>
  );
};

/** Lower-third chip naming the step; slides in from the left at the start of its segment. */
const CalloutChip: React.FC<{ text: string; tone: keyof typeof TONE; total: number }> = ({ text, tone, total }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { color, glyph } = TONE[tone];
  const p = pop(frame, 2, fps, 14);
  const out = prog(frame, total - 6, 6);
  return (
    <div style={{ position: "absolute", left: L.frameX - 28, top: L.frameY + L.frameH - 44, height: 60, display: "flex",
                  alignItems: "center", gap: 14, padding: "0 26px 0 10px", borderRadius: 999, background: color,
                  fontFamily: FONT, fontSize: 32, fontWeight: 800, color: V.ink, whiteSpace: "nowrap",
                  boxShadow: `0 10px 30px rgba(0,0,0,.45), 0 0 40px ${color}66`,
                  translate: `${(1 - p) * -80}px 0px`, opacity: Math.min(prog(frame, 2, 6), 1 - out) }}>
      <span style={{ width: 42, height: 42, borderRadius: 99, background: V.ink, color, display: "grid", placeItems: "center",
                     fontSize: 26, fontWeight: 900 }}>{glyph}</span>
      {text}
    </div>
  );
};
