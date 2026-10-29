import { AbsoluteFill, Img, staticFile } from "remotion";
import { Logo } from "./components/Chrome.tsx";
import { C, FONT, V } from "./theme.ts";

// Devpost image gallery (3:2, 1800x1200). Same visual language as the video and thumbnails. Every app image is a
// real capture of the running app with synthetic data; diagrams and numbers come from the code and measured results.
export type GalleryImage = { src: string; w: number; h: number };
export type GalleryProps = {
  index: number; total: number; title: string; caption: string; accent: string;
  images?: GalleryImage[]; phones?: GalleryImage[]; steps?: [string, string][]; stats?: [string, string][];
};

export const Gallery: React.FC<GalleryProps> = ({ index, total, title, caption, accent, images, phones, steps, stats }) => (
  <AbsoluteFill style={{ background: V.bg, fontFamily: FONT, overflow: "hidden" }}>
    <AbsoluteFill style={{ background: `radial-gradient(circle 700px at 1500px 900px, ${accent}44, transparent 70%), ` +
                                       `radial-gradient(circle 600px at 200px 120px, ${accent}26, transparent 70%)` }} />
    <AbsoluteFill style={{ backgroundImage: "radial-gradient(rgba(255,255,255,0.08) 1.5px, transparent 1.6px)",
                           backgroundSize: "36px 36px" }} />
    <div style={{ position: "absolute", left: 80, top: 64, right: 80, display: "flex", alignItems: "center", gap: 18 }}>
      <Logo size={52} />
      <span style={{ flex: 1 }} />
      <span style={{ border: `2px dashed ${V.amber}`, color: V.amber, borderRadius: 999, padding: "4px 18px", fontSize: 24,
                     fontWeight: 700 }}>{images || phones ? "Real app · synthetic data" : steps ? "Architecture" : "Measured locally"}</span>
      <span style={{ color: C.muted, fontSize: 24, fontWeight: 700 }}>{index} / {total}</span>
    </div>
    <div style={{ position: "absolute", left: 80, top: 150, width: 1640 }}>
      <div style={{ fontSize: 64, lineHeight: "72px", fontWeight: 900, color: "#fff", letterSpacing: "-0.015em" }}>{title}</div>
      <div style={{ height: 8, width: 220, borderRadius: 99, background: accent, margin: "18px 0 16px",
                    boxShadow: `0 0 24px ${accent}` }} />
      <div style={{ fontSize: 32, lineHeight: "42px", fontWeight: 600, color: C.muted, maxWidth: 1500 }}>{caption}</div>
    </div>
    <div style={{ position: "absolute", left: 80, right: 80, top: 400, bottom: 70, display: "flex", alignItems: "center",
                  justifyContent: "center", gap: 48 }}>
      {images ? <Shots images={images} accent={accent} /> : null}
      {phones ? phones.map((p, i) => <Phone key={p.src} image={p} accent={accent} tilt={(i - (phones.length - 1) / 2) * 5} />) : null}
      {steps ? <Steps steps={steps} /> : null}
      {stats ? <Stats stats={stats} /> : null}
    </div>
  </AbsoluteFill>
);

/** Real app crops stacked in white cards, scaled to fit the stage (crops are captured at 2x). */
const Shots: React.FC<{ images: GalleryImage[]; accent: string }> = ({ images, accent }) => {
  const maxW = 1560, maxH = 690, gap = 26, pad = 16;
  const widest = Math.max(...images.map((i) => i.w));
  const tall = images.reduce((n, i) => n + i.h, 0);
  // Crops are captured at 2x density, so enlarging them up to 1.6x stays sharp.
  const k = Math.min((maxW - 2 * pad) / widest, (maxH - gap * (images.length - 1) - images.length * 2 * pad) / tall, 1.6);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap, alignItems: "center" }}>
      {images.map((img) => (
        <div key={img.src} style={{ background: "#fff", borderRadius: 18, padding: pad, border: `4px solid ${accent}`,
                                    boxShadow: `0 0 60px ${accent}44, 0 24px 60px rgba(0,0,0,.5)` }}>
          <Img src={staticFile(img.src)} style={{ width: Math.round(img.w * k), height: Math.round(img.h * k), display: "block" }} />
        </div>
      ))}
    </div>
  );
};

const Phone: React.FC<{ image: GalleryImage; accent: string; tilt: number }> = ({ image, accent, tilt }) => {
  const w = 300, h = Math.round((image.h / image.w) * w);
  return (
    <div style={{ padding: 12, borderRadius: 46, rotate: `${tilt}deg`, background: "linear-gradient(145deg, #3a4558, #11161f)",
                  boxShadow: `0 0 0 3px #5b6678, 0 0 80px ${accent}55, 0 30px 70px rgba(0,0,0,.6)` }}>
      <div style={{ width: w, height: h, borderRadius: 36, overflow: "hidden", background: "#fff" }}>
        <Img src={staticFile(image.src)} style={{ width: w, height: h, display: "block" }} />
      </div>
    </div>
  );
};

const STEP_COLORS = [V.blue, V.violet, V.green, V.amber, V.teal, V.coral];
const Steps: React.FC<{ steps: [string, string][] }> = ({ steps }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 16, width: 1500 }}>
    {steps.map(([head, body], i) => {
      const color = STEP_COLORS[i % STEP_COLORS.length];
      return (
        <div key={head} style={{ display: "flex", alignItems: "center", gap: 24, padding: "14px 26px", borderRadius: 18,
                                 background: "rgba(15,26,49,0.92)", border: `3px solid ${color}`, boxShadow: `0 0 36px ${color}33` }}>
          <span style={{ width: 52, height: 52, flex: "none", borderRadius: 99, background: color, color: V.ink, display: "grid",
                         placeItems: "center", fontSize: 28, fontWeight: 900 }}>{i + 1}</span>
          <span style={{ width: 520, flex: "none", fontSize: 32, fontWeight: 800, color: "#fff" }}>{head}</span>
          <span style={{ fontSize: 26, lineHeight: "34px", fontWeight: 600, color: C.muted }}>{body}</span>
        </div>
      );
    })}
  </div>
);

const Stats: React.FC<{ stats: [string, string][] }> = ({ stats }) => (
  <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 740px)", gap: 28 }}>
    {stats.map(([n, label], i) => {
      const color = STEP_COLORS[i % STEP_COLORS.length];
      return (
        <div key={label} style={{ padding: "22px 32px", borderRadius: 22, background: "rgba(15,26,49,0.92)",
                                  border: `4px solid ${color}`, boxShadow: `0 0 50px ${color}33` }}>
          <div style={{ fontSize: 84, lineHeight: "92px", fontWeight: 900, color, fontVariantNumeric: "tabular-nums" }}>{n}</div>
          <div style={{ fontSize: 28, lineHeight: "36px", fontWeight: 700, color: "#fff" }}>{label}</div>
        </div>
      );
    })}
  </div>
);
