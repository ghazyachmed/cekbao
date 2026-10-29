import { useCurrentFrame, useVideoConfig } from "remotion";
import type { PlannedScene } from "../types.ts";
import { Header } from "../components/Chrome.tsx";
import { pop, prog } from "../motion.ts";
import { C, FONT, TONE, V } from "../theme.ts";

// The distinctive moment: one invoice, two payment dates, two policy versions. The date axis draws first, the two
// versions and the 1 September change follow the first sentence, and the two payments land with the last one.
// Dates, versions and accounts are the synthetic Aster Bay data (policyguard/seed.py); results are the app's own.
const X0 = 200, X1 = 1720, DAYS = 184;                      // 1 Jul 2026 .. 31 Dec 2026
const x = (day: number) => X0 + (day / DAYS) * (X1 - X0);
const MONTHS: [string, number][] = [["Jul", 0], ["Aug", 31], ["Sep", 62], ["Oct", 92], ["Nov", 123], ["Dec", 153]];
const SEP1 = 62, AUG14 = 44, NOV30 = 152, AXIS_Y = 560;

export const PolicyTimeline: React.FC<{ scene: PlannedScene; preview: boolean }> = ({ scene, preview }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Beats: the axis draws at once, the versions arrive with the first sentence, the payments with the last one.
  const beats = scene.beats ?? [18, 300];
  const [b0, b1, b2] = [0, beats[0], beats[beats.length - 1]];
  const [next, earlier] = scene.verdicts ?? ["Conflicts with the checked policy.", "Matches the checked policy."];
  const axis = prog(frame, b0, 24);
  const oldBar = prog(frame, b1, 20), newBar = prog(frame, b1 + 30, 24);
  const change = pop(frame, b1 + 18, fps, 10);
  return (
    <div style={{ position: "absolute", inset: 0, fontFamily: FONT }}>
      <Header left="Scenario B: the date chooses the policy version" preview={preview} accent={V.violet} />
      <div style={{ position: "absolute", left: 0, right: 0, top: 128, textAlign: "center", fontSize: 64, fontWeight: 900,
                    color: "#fff", letterSpacing: "-0.015em", opacity: prog(frame, 0, 10), scale: String(pop(frame, 0, fps, 12)) }}>
        One invoice, <span style={{ color: V.violet }}>two dates</span>, <span style={{ color: V.teal }}>two answers</span>
      </div>
      <InvoiceCard p={pop(frame, b0 + 10, fps, 13)} />
      {/* version bars */}
      <Bar from={X0 - 80} to={x(SEP1)} y={AXIS_Y - 120} color={V.blue} p={oldBar}
           label="Policy 2025.1" sub="account …9268 19 · until 31 Aug" />
      <Bar from={x(SEP1)} to={X1 + 80} y={AXIS_Y - 120} color={V.violet} p={newBar} arrow
           label="Policy 2026.1" sub="new account …5501 77 · from 1 Sep" />
      {/* axis */}
      <div style={{ position: "absolute", left: X0 - 80, top: AXIS_Y, height: 6, width: (X1 - X0 + 160) * axis, borderRadius: 99,
                    background: "rgba(255,255,255,0.8)" }} />
      {MONTHS.map(([m, d], i) => (
        <div key={m} style={{ position: "absolute", left: x(d) - 40, top: AXIS_Y + 18, width: 80, textAlign: "center",
                              fontSize: 30, fontWeight: 700, color: C.muted, opacity: prog(frame, b0 + 6 + i * 3, 8) }}>
          <div style={{ width: 4, height: 18, background: "rgba(255,255,255,0.7)", margin: "-30px auto 12px" }} />{m}
        </div>
      ))}
      <div style={{ position: "absolute", left: X1 + 40, top: AXIS_Y + 18, fontSize: 28, fontWeight: 700, color: C.muted,
                    opacity: prog(frame, b0 + 20, 8) }}>2026</div>
      {/* 1 September change */}
      <div style={{ position: "absolute", left: x(SEP1) - 3, top: AXIS_Y - 190, width: 6, height: 210 * change,
                    background: `repeating-linear-gradient(${V.amber} 0 12px, transparent 12px 22px)` }} />
      <div style={{ position: "absolute", left: x(SEP1) - 150, top: AXIS_Y - 236, width: 300, textAlign: "center",
                    fontSize: 28, fontWeight: 800, color: V.ink, background: V.amber, borderRadius: 999, padding: "4px 0",
                    scale: String(change) }}>1 Sep: new version</div>
      <Payment day={AUG14} label="Paid 14 Aug" verdict={earlier} at={b2} />
      <Payment day={NOV30} label="Due 30 Nov" verdict={next} at={b2 + 26} />
    </div>
  );
};

const InvoiceCard: React.FC<{ p: number }> = ({ p }) => (
  <div style={{ position: "absolute", left: 660, top: 214, width: 600, padding: "14px 24px", borderRadius: 18, background: "#fff",
                color: V.ink, boxShadow: `0 0 50px ${V.violet}66`, scale: String(p), opacity: Math.min(1, p * 2) }}>
    <div style={{ fontSize: 26, fontWeight: 700, color: "#4a5a6b" }}>Invoice from July · synthetic</div>
    <div style={{ fontSize: 32, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>Account …9268 19</div>
  </div>
);

const Bar: React.FC<{ from: number; to: number; y: number; color: string; p: number; label: string; sub: string; arrow?: boolean }> =
  ({ from, to, y, color, p, label, sub, arrow }) => (
    <div style={{ position: "absolute", left: from, top: y, height: 92, width: Math.max(0, (to - from) * p), overflow: "hidden",
                  borderRadius: arrow ? "18px 0 0 18px" : 18, background: `linear-gradient(90deg, ${color}33, ${color}cc)`,
                  border: `3px solid ${color}`, boxShadow: `0 0 40px ${color}55`, fontFamily: FONT }}>
      <div style={{ padding: "8px 22px", whiteSpace: "nowrap", textAlign: arrow ? "left" : "right" }}>
        <div style={{ fontSize: 32, fontWeight: 900, color: "#fff" }}>{label}</div>
        <div style={{ fontSize: 26, fontWeight: 700, color: "#fff", opacity: 0.92 }}>{sub}</div>
      </div>
    </div>
  );

const Payment: React.FC<{ day: number; label: string; verdict: string; at: number }> = ({ day, label, verdict, at }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const drop = pop(frame, at, fps, 11);
  const stamp = pop(frame, at + 16, fps, 9);
  const tone = /^conflict/i.test(verdict) ? TONE.bad : /^match/i.test(verdict) ? TONE.ok : TONE.warn;
  const cx = x(day);
  return (
    <>
      <div style={{ position: "absolute", left: cx - 3, top: 316, width: 6, height: (AXIS_Y - 316) * drop,
                    background: `linear-gradient(${"#ffffff"}00, ${tone.color})` }} />
      <div style={{ position: "absolute", left: cx - 22, top: AXIS_Y - 19, width: 44, height: 44, borderRadius: 99,
                    background: tone.color, border: "5px solid #fff", scale: String(drop), boxShadow: `0 0 40px ${tone.color}` }} />
      <div style={{ position: "absolute", left: cx - 300, top: AXIS_Y + 86, width: 600, textAlign: "center", fontFamily: FONT,
                    scale: String(stamp), opacity: Math.min(1, stamp * 2) }}>
        <div style={{ fontSize: 34, fontWeight: 800, color: "#fff" }}>{label}</div>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 12, marginTop: 10, padding: "8px 22px 8px 10px",
                      borderRadius: 999, background: tone.color, color: V.ink, fontSize: 30, fontWeight: 900, whiteSpace: "nowrap",
                      boxShadow: `0 0 50px ${tone.color}88`, rotate: `${(1 - stamp) * -8}deg` }}>
          <span style={{ width: 40, height: 40, borderRadius: 99, background: V.ink, color: tone.color, display: "grid",
                         placeItems: "center", fontSize: 24 }}>{tone.glyph}</span>
          {verdict.replace(/\.$/, "")}
        </div>
      </div>
    </>
  );
};
