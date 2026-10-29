import { AbsoluteFill, Img, staticFile } from "remotion";
import { Logo } from "./components/Chrome.tsx";
import { FONT, TONE, V, type Tone } from "./theme.ts";

// YouTube thumbnail (designed at 1920x1080, rendered at --scale=2 for the 3840x2160 master).
// Big type with one neon word, a tilted phone showing a real capture of the app (synthetic data), a glowing
// result chip that restates the app's own result, and a truth badge. The lower-right corner stays empty
// because YouTube draws the duration there.
export type ThumbImage = { src: string; w: number; h: number };
export type HeadlineLine = { text: string; neon?: boolean; outline?: boolean };
export type ThumbnailProps = {
  lines: HeadlineLine[]; accent: string; phone: ThumbImage | null; note: string;
  chip?: { text: string; tone: Tone }; dates?: { label: string; result: string; tone: Tone }[];
  // Legacy fields kept so older props files still render.
  headline?: string; images?: ThumbImage[];
};

export const Thumbnail: React.FC<ThumbnailProps> = ({ lines, accent, phone, note, chip, dates }) => {
  const size = Math.min(190, ...lines.map((l) => Math.floor(1000 / (l.text.length * 0.66))));
  return (
    <AbsoluteFill style={{ background: V.bg, fontFamily: FONT, overflow: "hidden" }}>
      {/* diagonal colour wedge and glow behind the phone */}
      <AbsoluteFill style={{ background: `linear-gradient(115deg, transparent 0 56%, ${accent}33 56% 100%)` }} />
      <AbsoluteFill style={{ background: `radial-gradient(circle 620px at 1420px 520px, ${accent}66, transparent 70%)` }} />
      <AbsoluteFill style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.05) 2px, transparent 2px), " +
                                              "linear-gradient(90deg, rgba(255,255,255,0.05) 2px, transparent 2px)",
                             backgroundSize: "80px 80px" }} />
      <div style={{ position: "absolute", left: 96, top: 70 }}><Logo size={70} /></div>
      <div style={{ position: "absolute", left: 90, top: 200, width: 1080 }}>
        {lines.map((l, i) => (
          <div key={i} style={{
            fontSize: size, lineHeight: `${Math.round(size * 0.98)}px`, fontWeight: 900, letterSpacing: "-0.03em",
            textTransform: "uppercase", whiteSpace: "nowrap",
            color: l.outline ? "transparent" : l.neon ? accent : "#ffffff",
            WebkitTextStroke: l.outline ? `7px ${accent}` : undefined,
            textShadow: l.neon || l.outline ? `0 0 28px ${accent}, 0 0 70px ${accent}aa` : "0 8px 30px rgba(0,0,0,.6)",
          }}>{l.text}</div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 96, top: 900, display: "flex", gap: 18 }}>
        <span style={{ background: V.teal, color: V.ink, borderRadius: 999, padding: "10px 30px", fontSize: 38,
                       fontWeight: 900, letterSpacing: "0.02em", boxShadow: `0 0 40px ${V.teal}88` }}>{note}</span>
      </div>
      {phone ? <Phone image={phone} accent={accent} /> : null}
      {chip ? <ResultChip text={chip.text} tone={chip.tone} /> : null}
      {dates ? (
        <div style={{ position: "absolute", left: 1010, top: 690, display: "flex", flexDirection: "column", gap: 22 }}>
          {dates.map((d) => <DateChip key={d.label} {...d} />)}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const Phone: React.FC<{ image: ThumbImage; accent: string }> = ({ image, accent }) => {
  const w = 430, h = Math.round((image.h / image.w) * w);
  return (
    <div style={{ position: "absolute", left: 1230, top: 70, rotate: "8deg", padding: 16, borderRadius: 64,
                  background: "linear-gradient(145deg, #3a4558, #11161f)",
                  boxShadow: `0 0 0 3px #5b6678, 0 0 120px ${accent}88, 0 40px 90px rgba(0,0,0,.7)` }}>
      <div style={{ width: w, height: h, borderRadius: 48, overflow: "hidden", position: "relative", background: "#fff" }}>
        <Img src={staticFile(image.src)} style={{ width: w, height: h, display: "block" }} />
      </div>
      <div style={{ position: "absolute", left: "50%", top: 30, width: 120, height: 30, marginLeft: -60, borderRadius: 99,
                    background: "#0b0f16" }} />
    </div>
  );
};

/** Restates the app's own result in large type so it reads at 160x90. */
const ResultChip: React.FC<{ text: string; tone: Tone }> = ({ text, tone }) => {
  const { color, glyph } = TONE[tone];
  return (
    <div style={{ position: "absolute", left: 930, top: 720, display: "flex", alignItems: "center", gap: 20, rotate: "-4deg",
                  background: color, color: V.ink, borderRadius: 28, padding: "16px 32px 16px 16px", fontSize: 52, fontWeight: 900,
                  letterSpacing: "-0.01em", boxShadow: `0 0 0 6px ${V.bg}, 0 0 80px ${color}, 0 20px 50px rgba(0,0,0,.6)` }}>
      <span style={{ width: 84, height: 84, borderRadius: 99, background: V.ink, color, display: "grid", placeItems: "center",
                     fontSize: 56 }}>{glyph}</span>
      {text}
    </div>
  );
};

const DateChip: React.FC<{ label: string; result: string; tone: Tone }> = ({ label, result, tone }) => {
  const { color, glyph } = TONE[tone];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18, background: "rgba(6,11,24,0.92)", border: `5px solid ${color}`,
                  borderRadius: 24, padding: "10px 26px 10px 12px", boxShadow: `0 0 60px ${color}aa`, rotate: "-4deg" }}>
      <span style={{ width: 70, height: 70, borderRadius: 99, background: color, color: V.ink, display: "grid", placeItems: "center",
                     fontSize: 46, fontWeight: 900 }}>{glyph}</span>
      <span style={{ fontSize: 54, fontWeight: 900, color: "#fff" }}>{label}</span>
      <span style={{ fontSize: 46, fontWeight: 900, color }}>{result}</span>
    </div>
  );
};
