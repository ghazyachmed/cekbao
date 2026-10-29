import { Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { PlannedScene } from "../types.ts";
import { Header, Logo } from "../components/Chrome.tsx";
import { lerp, onCurve, pop, prog, windowed } from "../motion.ts";
import { C, FONT, V } from "../theme.ts";

// Animated problem statement, timed to the five narration beats:
// 0 the email, 1 "would you pay it?" with a real capture of the app, 2 where the money would go,
// 3 the reported scam pattern (official source), 4 what CEKBAO compares.
// All names and accounts are the synthetic Scenario A data (policyguard/seed.py).
export const Intro: React.FC<{ scene: PlannedScene; preview: boolean }> = ({ scene, preview }) => {
  const frame = useCurrentFrame();
  const b = scene.beats ?? [18, 120, 220, 360, 520];
  return (
    <>
      <Header left="Why check a payment instruction?" preview={preview} accent={V.coral} />
      <Email frame={frame} b0={b[0]} b1={b[1]} until={b[2]} />
      {scene.teaser ? <Teaser frame={frame} at={b[1]} until={b[2]} still={scene.teaser} /> : null}
      <MoneyPaths frame={frame} at={b[2]} until={b[3]} />
      <Reported frame={frame} at={b[3]} until={b[4]} />
      <Compare frame={frame} at={b[4]} />
    </>
  );
};

const Email: React.FC<{ frame: number; b0: number; b1: number; until: number }> = ({ frame, b0, b1, until }) => {
  const { fps } = useVideoConfig();
  const enter = pop(frame, 0, fps, 13);
  const shrink = prog(frame, b1, 22);
  const rows: [string, string, boolean][] = [
    ["From", "Student Finance Team · finance-update@asterbay-payments.example", false],
    ["Subject", "Updated tuition payment details: action required", false],
    ["", "Please pay your Term 2 balance of GBP 9,250.00 by 15 November 2026.", false],
    ["Payee", "Northbridge Education Services Ltd", true],
    ["IBAN", "GB71 SYNT 7777 0000 1234 56", true],
  ];
  const sticker = pop(frame, b0 + 48, fps, 8);
  return (
    <div style={{ position: "absolute", left: 360, top: 170, width: 1200, opacity: windowed(frame, 0, until),
                  scale: String(lerp(interpolate(enter, [0, 1], [0.8, 1]), 0.52, shrink)),
                  translate: `${lerp((1 - enter) * 120, -450, shrink)}px ${lerp(0, 150, shrink)}px`,
                  rotate: `${lerp((1 - enter) * -6, -3, shrink)}deg`, transformOrigin: "50% 50%" }}>
      <div style={{ background: "#ffffff", borderRadius: 26, padding: "34px 44px", fontFamily: FONT, color: V.ink,
                    boxShadow: `0 0 0 4px ${V.coral}, 0 0 90px ${V.coral}55, 0 30px 80px rgba(0,0,0,.5)` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 18 }}>
          <MailIcon />
          <span style={{ fontSize: 30, fontWeight: 800 }}>Inbox</span>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 24, fontWeight: 700, color: "#7a4a00", background: "#fff3c4", border: "2px dashed #b58100",
                         borderRadius: 999, padding: "2px 14px" }}>Synthetic example</span>
        </div>
        {rows.map(([k, v, hot], i) => {
          const p = prog(frame, b0 + 4 + i * 6, 12);
          const mark = prog(frame, b0 + 40 + (i - 3) * 6, 14);
          return (
            <div key={i} style={{ display: "flex", gap: 18, padding: "10px 0", borderTop: i ? "2px solid #e3e8ee" : "none",
                                  opacity: p, translate: `${(1 - p) * 30}px 0px`, position: "relative" }}>
              {hot ? <div style={{ position: "absolute", left: -12, top: 4, bottom: 4, borderRadius: 10,
                                   width: `calc(${mark * 100}% + 24px)`, background: `${V.coral}44` }} /> : null}
              {k ? <span style={{ width: 130, flex: "none", fontSize: 30, fontWeight: 700, color: "#4a5a6b", position: "relative" }}>{k}</span> : null}
              <span style={{ fontSize: 32, lineHeight: "42px", fontWeight: hot ? 800 : 500, position: "relative",
                             color: hot ? "#a3001a" : V.ink, fontVariantNumeric: "tabular-nums" }}>{v}</span>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", right: -40, top: 300, background: V.coral, color: V.ink, fontFamily: FONT,
                    fontWeight: 900, fontSize: 40, padding: "10px 26px", borderRadius: 14, rotate: "8deg",
                    scale: String(sticker), boxShadow: `0 0 50px ${V.coral}aa` }}>NEW ACCOUNT</div>
    </div>
  );
};

const MailIcon = () => (
  <svg width="46" height="34" viewBox="0 0 46 34">
    <rect x="2" y="2" width="42" height="30" rx="5" fill={V.coral} />
    <path d="M4 5 L23 19 L42 5" stroke={V.ink} strokeWidth="3.5" fill="none" strokeLinejoin="round" />
  </svg>
);

const Teaser: React.FC<{ frame: number; at: number; until: number; still: { src: string; width: number; height: number } }> =
  ({ frame, at, until, still }) => {
    const { fps } = useVideoConfig();
    const q = pop(frame, at + 4, fps, 13);
    const phone = pop(frame, at + 18, fps, 13);
    const w = 270, h = Math.round((still.height / still.width) * w);
    const o = windowed(frame, at, until);
    return (
      <>
        <div style={{ position: "absolute", left: 0, right: 0, top: 130, textAlign: "center", fontFamily: FONT, opacity: o }}>
          <span style={{ display: "inline-block", fontSize: 92, fontWeight: 900, color: "#fff", letterSpacing: "-0.02em",
                         scale: String(q), textShadow: `0 0 40px ${V.coral}88` }}>
            Would you pay it<span style={{ color: V.coral }}>?</span>
          </span>
        </div>
        <div style={{ position: "absolute", left: 950, top: 420, width: 440, fontFamily: FONT, opacity: o * prog(frame, at + 30, 8),
                      translate: `${(1 - prog(frame, at + 30, 16)) * 40}px 0px` }}>
          <Logo size={64} />
          <div style={{ fontSize: 36, fontWeight: 800, color: V.teal, marginTop: 14 }}>checks before you pay</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: C.muted, marginTop: 10 }}>Real app screen · synthetic data</div>
        </div>
        <div style={{ position: "absolute", left: 1430, top: 230, padding: 12, borderRadius: 46, opacity: o * Math.min(1, phone * 2),
                      background: "linear-gradient(145deg, #3a4558, #11161f)", rotate: `${6 + (1 - phone) * 14}deg`,
                      translate: `${(1 - phone) * 300}px 0px`,
                      boxShadow: `0 0 0 3px #5b6678, 0 0 90px ${V.coral}77, 0 30px 70px rgba(0,0,0,.6)` }}>
          <div style={{ width: w, height: h, borderRadius: 36, overflow: "hidden", background: "#fff" }}>
            <Img src={staticFile(still.src)} style={{ width: w, height: h, display: "block" }} />
          </div>
        </div>
      </>
    );
  };

const MoneyPaths: React.FC<{ frame: number; at: number; until: number }> = ({ frame, at, until }) => {
  const { fps } = useVideoConfig();
  const o = windowed(frame, at, until);
  if (o <= 0) return null;
  const up = prog(frame, at + 6, 24), down = prog(frame, at + 22, 24);
  const start: [number, number] = [560, 500];
  const P = { up: { c: [860, 220] as [number, number], end: [1180, 300] as [number, number] },
              down: { c: [860, 800] as [number, number], end: [1180, 700] as [number, number] } };
  const coinT = prog(frame, at + 46, 40);
  const [cx, cy] = onCurve(start, P.down.c, P.down.end, coinT);
  const neq = pop(frame, at + 70, fps, 8);
  const path = (end: [number, number], c: [number, number]) => `M ${start[0]} ${start[1]} Q ${c[0]} ${c[1]} ${end[0]} ${end[1]}`;
  return (
    <div style={{ position: "absolute", inset: 0, opacity: o, fontFamily: FONT }}>
      <svg width="1920" height="1080" style={{ position: "absolute", inset: 0 }}>
        <path d={path(P.up.end, P.up.c)} stroke={V.teal} strokeWidth="8" fill="none" strokeLinecap="round"
              pathLength={1} strokeDasharray="1" strokeDashoffset={1 - up} />
        <path d={path(P.down.end, P.down.c)} stroke={V.coral} strokeWidth="8" fill="none" strokeLinecap="round"
              pathLength={1} strokeDasharray="1" strokeDashoffset={1 - down} />
        <Building x={300} y={380} p={prog(frame, at, 20)} />
      </svg>
      <div style={{ position: "absolute", left: 210, top: 640, width: 380, textAlign: "center", fontSize: 30, fontWeight: 700,
                    color: "#fff", opacity: prog(frame, at + 8, 10) }}>Aster Bay University<br />
        <span style={{ fontSize: 26, color: V.amber }}>synthetic</span></div>
      <PathCard x={1190} y={190} color={V.teal} label="The university's policy" name="Aster Bay University"
                account="GB94 SYNT 4000 0055 5501 77" p={pop(frame, at + 26, fps, 14)} />
      <PathCard x={1190} y={590} color={V.coral} label="The email asks for" name="Northbridge Education Services Ltd"
                account="GB71 SYNT 7777 0000 1234 56" p={pop(frame, at + 42, fps, 14)} />
      {coinT > 0 && coinT < 1 ? (
        <div style={{ position: "absolute", left: cx - 34, top: cy - 34, width: 68, height: 68, borderRadius: 99, background: V.amber,
                      color: V.ink, display: "grid", placeItems: "center", fontSize: 38, fontWeight: 900,
                      boxShadow: `0 0 40px ${V.amber}` }}>£</div>
      ) : null}
      <div style={{ position: "absolute", left: 1440, top: 430, width: 120, height: 120, borderRadius: 99, background: V.coral,
                    color: V.ink, display: "grid", placeItems: "center", fontSize: 84, fontWeight: 900, scale: String(neq),
                    boxShadow: `0 0 70px ${V.coral}` }}>≠</div>
    </div>
  );
};

const PathCard: React.FC<{ x: number; y: number; color: string; label: string; name: string; account: string; p: number }> =
  ({ x, y, color, label, name, account, p }) => (
    <div style={{ position: "absolute", left: x, top: y, width: 620, padding: "22px 30px", borderRadius: 22,
                  background: "rgba(15,26,49,0.92)", border: `4px solid ${color}`, boxShadow: `0 0 60px ${color}55`,
                  scale: String(interpolate(p, [0, 1], [0.6, 1])), opacity: Math.min(1, p * 1.5), transformOrigin: "0% 50%" }}>
      <div style={{ fontSize: 28, fontWeight: 800, color }}>{label}</div>
      <div style={{ fontSize: 36, fontWeight: 800, color: "#fff", marginTop: 6 }}>{name}</div>
      <div style={{ fontSize: 32, fontWeight: 600, color: C.muted, marginTop: 4, fontVariantNumeric: "tabular-nums" }}>{account}</div>
    </div>
  );

/** Line-drawn institution building; `p` draws the strokes. */
const Building: React.FC<{ x: number; y: number; p: number }> = ({ x, y, p }) => {
  const s = { stroke: "#ffffff", strokeWidth: 7, fill: "none", strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
              pathLength: 1, strokeDasharray: "1", strokeDashoffset: 1 - p };
  return (
    <g transform={`translate(${x} ${y})`}>
      <path d="M 10 80 L 130 20 L 250 80 Z" {...s} />
      {[40, 90, 140, 190, 230].map((cx, i) => <path key={i} d={`M ${cx - 10} 100 V 220`} {...s} />)}
      <path d="M 0 240 H 260 M 10 100 H 250" {...s} />
    </g>
  );
};

const Reported: React.FC<{ frame: number; at: number; until: number }> = ({ frame, at, until }) => {
  const { fps } = useVideoConfig();
  const o = windowed(frame, at, until);
  if (o <= 0) return null;
  const n = Math.round(interpolate(frame, [at + 6, at + 40], [0, 20], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const plus = pop(frame, at + 42, fps, 8);
  return (
    <div style={{ position: "absolute", inset: 0, opacity: o, fontFamily: FONT }}>
      <div style={{ position: "absolute", left: 140, top: 150, fontSize: 28, fontWeight: 800, color: V.ink, background: V.amber,
                    borderRadius: 999, padding: "4px 20px" }}>Reported evidence · Singapore</div>
      <div style={{ position: "absolute", left: 130, top: 200, fontSize: 280, lineHeight: "300px", fontWeight: 900, color: V.coral,
                    textShadow: `0 0 60px ${V.coral}99`, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.03em" }}>
        {n}<span style={{ display: "inline-block", scale: String(plus) }}>+</span>
      </div>
      <div style={{ position: "absolute", left: 140, top: 520, width: 860 }}>
        <div style={{ fontSize: 44, lineHeight: "54px", fontWeight: 800, color: "#fff", opacity: prog(frame, at + 20, 12) }}>
          cases of scams impersonating schools, reported since March 2026
        </div>
        <div style={{ fontSize: 38, fontWeight: 800, color: V.amber, marginTop: 18, opacity: prog(frame, at + 36, 12) }}>
          Losses of at least S$31,000
        </div>
        <div style={{ fontSize: 32, fontWeight: 600, color: C.muted, marginTop: 12, opacity: prog(frame, at + 50, 12) }}>
          Emails demanded urgent payment of school fees.
        </div>
      </div>
      <div style={{ position: "absolute", left: 1110, top: 230, display: "grid", gridTemplateColumns: "repeat(5, 120px)", gap: 22 }}>
        {Array.from({ length: 20 }, (_, i) => {
          const p = pop(frame, at + 8 + i * 1.6, fps, 10);
          return (
            <svg key={i} width="120" height="88" viewBox="0 0 120 88" style={{ scale: String(p), opacity: Math.min(1, p * 2) }}>
              <rect x="4" y="4" width="112" height="80" rx="12" fill="rgba(255,107,125,0.16)" stroke={V.coral} strokeWidth="5" />
              <path d="M 10 12 L 60 50 L 110 12" stroke={V.coral} strokeWidth="5" fill="none" strokeLinejoin="round" />
            </svg>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 140, top: 836, fontSize: 28, fontWeight: 600, color: C.muted,
                    opacity: prog(frame, at + 30, 12) }}>
        Source: Singapore Police Force advisory, 19 March 2026 (police.gov.sg). Figures as reported.
      </div>
    </div>
  );
};

const Compare: React.FC<{ frame: number; at: number }> = ({ frame, at }) => {
  const { fps } = useVideoConfig();
  const o = windowed(frame, at);
  if (o <= 0) return null;
  const steps: [string, string, string][] = [
    ["1", "The instruction", V.blue], ["2", "The policy valid on the payment date", V.violet], ["3", "Result, evidence, next step", V.teal],
  ];
  return (
    <div style={{ position: "absolute", inset: 0, opacity: o, fontFamily: FONT }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 200, display: "flex", justifyContent: "center",
                    scale: String(pop(frame, at, fps, 10)) }}>
        <Logo size={120} />
      </div>
      <div style={{ position: "absolute", left: 120, right: 120, top: 470, display: "flex", alignItems: "center", gap: 26,
                    justifyContent: "center" }}>
        {steps.map(([n, label, color], i) => {
          const p = pop(frame, at + 16 + i * 14, fps, 12);
          return (
            <div key={n} style={{ display: "flex", alignItems: "center", gap: 26 }}>
              {i ? <div style={{ width: 90 * prog(frame, at + 10 + i * 14, 10), height: 8, borderRadius: 99,
                                 background: `linear-gradient(90deg, ${steps[i - 1][2]}, ${color})` }} /> : null}
              <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "18px 28px", borderRadius: 22, flex: "none",
                            background: "rgba(15,26,49,0.92)", border: `4px solid ${color}`, boxShadow: `0 0 50px ${color}55`,
                            scale: String(p), opacity: Math.min(1, p * 2) }}>
                <span style={{ width: 52, height: 52, borderRadius: 99, background: color, color: V.ink, display: "grid",
                               placeItems: "center", fontSize: 30, fontWeight: 900 }}>{n}</span>
                <span style={{ fontSize: 34, lineHeight: "42px", fontWeight: 800, color: "#fff", maxWidth: 360 }}>{label}</span>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 690, textAlign: "center", fontSize: 32, fontWeight: 650,
                    color: C.muted, opacity: prog(frame, at + 60, 14) }}>
        It never moves money, and it never confirms a payment.
      </div>
    </div>
  );
};
