// Real CEKBAO app capture scenes (Scenarios A, B, C). Every image is a real
// screenshot of the running sandbox app at the pinned commit (see captures/manifest.json).
import React from "react";
import { AbsoluteFill, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import { apiResult, box, center, clickBox } from "../captures";
import { at, CaptureWindow, Shot, WIN } from "../components/Capture";
import { C, FONT, MONO } from "../theme";
import { fade, prog } from "../anim";
import { Canvas, curve, Head, Stroke, Txt } from "../components/Drawn";

const useT = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps;
};

const VIEW = { s: 0.875, cx: 960 };

/** One short note pill inside the capture window (one overlay at a time). */
const Note: React.FC<{ t: number; t0: number; t1: number; text: string; color: string; y?: number }> = ({ t, t0, t1, text, color, y = WIN.y + WIN.bar + 18 }) => {
  const o = fade(t, t0, 0.4, t1);
  if (o <= 0) return null;
  return (
    <div style={{ position: "absolute", right: 1920 - WIN.x - WIN.w + 22, top: y, opacity: o, fontFamily: FONT, fontSize: 28, fontWeight: 800, color: "#070B10", background: color, borderRadius: 10, padding: "8px 18px", boxShadow: "0 4px 18px rgba(0,0,0,.45)" }}>
      {text}
    </div>
  );
};

const Hold: React.FC<{ at: number }> = ({ at: s }) => {
  const { fps } = useVideoConfig();
  return (
    <Sequence from={Math.round(s * fps)} durationInFrames={30} layout="none">
      <Audio src={staticFile("audio/sfx_hold.wav")} volume={0.32} />
    </Sequence>
  );
};

// ---------------------------------------------------------------- Scenario A
export const DemoA: React.FC = () => {
  const t = useT();
  const verdict = box("A_full", "verdict");
  const rows = (i: number) => box("A_full", "checkRows", i);
  const locked = box("A_full", "locked");
  const contact = box("A_full", "contact");
  const draft = { x: 438, y: 426, w: 1044, h: 240 }; // textarea in A06_draft (viewport image)
  const checksMid = (rows(1).y + rows(5).y + rows(5).h) / 2;
  const shots: Shot[] = [
    { img: "A01_signin", t0: 0, t1: 5.6, ...VIEW, cy: 600,
      clicks: [at(clickBox("A01_signin", "persona"), 2.0), at(clickBox("A01_signin"), 4.4)],
      marks: [{ box: clickBox("A01_signin", "persona"), color: C.teal, label: "Synthetic persona", at: 0.9, until: 3.6 }] },
    { img: "A02_request_tab", t0: 5.6, t1: 8.6, ...VIEW, cy: 560, clicks: [at(clickBox("A02_request_tab"), 7.9)] },
    { img: "A03_sample_loaded", t0: 8.6, t1: 13.2, ...VIEW, cy: 600, clicks: [at(clickBox("A03_sample_loaded"), 12.5)] },
    { img: "A_full", t0: 13.2, t1: 20.2, s: 1.4, cx: 960, cy: verdict.y + 230,
      marks: [{ box: verdict, color: C.coral, label: "CONFLICT · payment held", at: 14.0, until: 19.9, labelBelow: true }] },
    { img: "A_full", t0: 20.2, t1: 27.0, s: 1.2, cx: 960, cy: checksMid,
      marks: [
        { box: rows(1), color: C.coral, at: 20.9 },
        { box: rows(3), color: C.coral, at: 22.0 },
        { box: rows(5), color: C.coral, at: 23.2 },
      ] },
    { img: "A_full", t0: 27.0, t1: 32.0, s: 1.4, cx: 960, cy: locked.y + 40,
      marks: [{ box: locked, color: C.coral, label: "Plan blocked", at: 27.6 }] },
    { img: "A_full", t0: 32.0, t1: 35.8, s: 1.4, cx: 960, cy: center(contact).y,
      marks: [{ box: contact, color: C.teal, label: "From the registry, not the message", at: 32.5 }] },
    { img: "A06_draft", t0: 35.8, t1: 39.6, s: 1.2, cx: 960, cy: 560,
      marks: [{ box: draft, color: C.teal, label: "Unsent draft", at: 36.3 }] },
    { img: "A09_locked", t0: 39.6, t1: 44, ...VIEW, cy: 540 },
  ];
  const r409 = apiResult("Ayu proposes a plan");
  const o409 = fade(t, 39.9, 0.4);
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <CaptureWindow shots={shots} label="Real app · Scenario A · synthetic data">
        {o409 > 0 ? (
          <div style={{ position: "absolute", left: WIN.x + 120, top: WIN.y + 190, width: WIN.w - 240, opacity: o409, background: "rgba(7,11,16,0.94)", border: `2px solid ${C.coral}`, borderRadius: 16, padding: "28px 36px", fontFamily: MONO, fontSize: 28, color: C.line, lineHeight: 1.5 }}>
            <div style={{ fontFamily: FONT, fontSize: 24, fontWeight: 700, letterSpacing: 2, color: C.dim, textTransform: "uppercase", marginBottom: 12 }}>Real server response, captured {"2026-10-20"}</div>
            <div>{r409.method} /api/cases/…/plan/propose</div>
            <div style={{ color: C.coral, fontWeight: 700 }}>HTTP {r409.status}</div>
            <div style={{ color: C.dim }}>{r409.body}</div>
          </div>
        ) : null}
      </CaptureWindow>
      <Hold at={13.6} />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- Scenario B
export const DemoB: React.FC = () => {
  const t = useT();
  const verdict = box("B_full", "verdict");
  const card = (i: number) => box("B_full", "slipCards", i);
  const shots: Shot[] = [
    { img: "B01_signin", t0: 0, t1: 4.4, ...VIEW, cy: 600, clicks: [at(clickBox("B01_signin", "persona"), 1.6), at(clickBox("B01_signin"), 3.6)] },
    { img: "B02_tabs", t0: 4.4, t1: 6.8, ...VIEW, cy: 450, clicks: [at(clickBox("B02_tabs"), 6.1)] },
    { img: "B03_slips_tab", t0: 6.8, t1: 9.4, ...VIEW, cy: 520, clicks: [at(clickBox("B03_slips_tab"), 8.7)] },
    { img: "B04_slips_loaded", t0: 9.4, t1: 12.6, ...VIEW, cy: 680, clicks: [at(clickBox("B04_slips_loaded"), 11.9)] },
    { img: "B_full", t0: 12.6, t1: 14.6, s: 1.4, cx: 960, cy: verdict.y + 180 },
    { img: "B_full", t0: 14.6, t1: 19.0, s: 1.4, cx: 960, cy: center(card(0)).y - 40,
      marks: [{ box: card(0), color: C.teal, label: "Matches the synthetic ledger", at: 15.2 }] },
    { img: "B_full", t0: 19.0, t1: 26.8, s: 1.4, cx: 960, cy: center(card(1)).y - 40,
      marks: [{ box: card(1), color: C.gold, label: "PAYMENT_UNCONFIRMED", at: 19.6 }] },
    { img: "B_full", t0: 26.8, t1: 42, s: 1.4, cx: 960, cy: center(card(2)).y - 40,
      marks: [{ box: card(2), color: C.coral, label: "CONFLICT · personal account", at: 27.4, until: 33.6 }] },
  ];
  const d = prog(t, 33.6, 34.2);
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <CaptureWindow shots={shots} label="Real app · Scenario B · synthetic data">
        <Note t={t} t0={7.4} t1={12.4} text="Bank feed and ledger: synthetic sandbox data" color={C.gold} />
        {d > 0 ? (
          <div style={{ position: "absolute", left: WIN.x, top: WIN.y + WIN.bar, width: WIN.w, height: WIN.h - WIN.bar, background: `rgba(7,11,16,${0.9 * d})` }} />
        ) : null}
      </CaptureWindow>
      {d > 0 ? (
        <Canvas>
          <Txt x={960} y={300} t={t} t0={34.0} size={68} weight={900} anchor="middle" lines={["A slip is not proof of settlement"]} />
          {[{ x: 260, label: "Slip", sub: "student's claim", c: C.line, t0: 35.0 },
            { x: 830, label: "Bank feed", sub: "synthetic sandbox", c: C.line, t0: 36.2 },
            { x: 1400, label: "Institution ledger", sub: "synthetic sandbox", c: C.teal, t0: 37.4 }].map((n, i) => (
            <g key={i}>
              <Txt x={n.x + 130} y={480} t={t} t0={n.t0} size={40} weight={800} anchor="middle" color={n.c} lines={[n.label]} />
              <Txt x={n.x + 130} y={530} t={t} t0={n.t0 + 0.2} size={28} anchor="middle" color={C.dim} lines={[n.sub]} />
              {i < 2 ? (<><Stroke d={curve(n.x + 330, 470, n.x + 520, 470, 0.4)} t={t} t0={n.t0 + 0.6} dur={0.6} color={C.dim} /><Head x={n.x + 522} y={470} t={t} t0={n.t0 + 1.1} color={C.dim} /></>) : null}
            </g>
          ))}
          <Txt x={1530} y={610} t={t} t0={38.4} size={30} weight={700} anchor="middle" color={C.teal} lines={["only this confirms payment"]} />
        </Canvas>
      ) : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- Scenario C
export const DemoC: React.FC = () => {
  const t = useT();
  const verdict = box("C_full", "verdict");
  const results = box("C_full", "resultGrid");
  const plan = box("C_full", "plan");
  const shots: Shot[] = [
    { img: "C01_signin", t0: 0, t1: 3.4, ...VIEW, cy: 600, clicks: [at(clickBox("C01_signin", "persona"), 1.2), at(clickBox("C01_signin"), 2.7)] },
    { img: "C02_sample_loaded", t0: 3.4, t1: 6.2, ...VIEW, cy: 600, clicks: [at(clickBox("C02_sample_loaded"), 5.6)] },
    { img: "C_full", t0: 6.2, t1: 13.6, s: 1.4, cx: 960, cy: verdict.y + 200,
      marks: [{ box: verdict, color: C.teal, label: "MATCHED_SOURCE", at: 6.9, until: 9.8, labelBelow: true }] },
    { img: "C05_quotes_form", t0: 13.6, t1: 17.4, ...VIEW, cy: 560, clicks: [at(clickBox("C05_quotes_form"), 16.7)] },
    { img: "C_full", t0: 17.4, t1: 23.6, s: 1.4, cx: 960, cy: center(results).y - 30,
      marks: [{ box: results, color: C.teal, label: "Lowest all-in cost · illustrative quotes", at: 18.2 }] },
    { img: "C08_plan_proposed", t0: 23.6, t1: 27.6, ...VIEW, cy: 520, clicks: [at(clickBox("C08_plan_proposed"), 26.8)] },
    { img: "C_full", t0: 27.6, t1: 42, s: 1.3, cx: 960, cy: center(plan).y,
      marks: [{ box: plan, color: C.teal, label: "Approved by the student", at: 28.2, until: 30.4 }] },
  ];
  const big = fade(t, 30.6, 0.5);
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <CaptureWindow shots={shots} label="Real app · Scenario C · synthetic data">
        <Note t={t} t0={10.0} t1={13.4} text="Registry match ≠ bank confirmation" color={C.gold} />
        {big > 0 ? (
          <div style={{ position: "absolute", left: WIN.x + 260, top: WIN.y + 220, width: WIN.w - 520, opacity: big, textAlign: "center", background: "rgba(7,11,16,0.94)", border: `3px solid ${C.line}`, borderRadius: 20, padding: "34px 40px", fontFamily: FONT, color: C.line }}>
            <div style={{ fontSize: 112, fontWeight: 900, letterSpacing: 4, lineHeight: 1 }}>NOT EXECUTED</div>
            <div style={{ fontSize: 34, color: C.dim, marginTop: 18 }}>Sandbox plan only. No money moves. No bank connection.</div>
          </div>
        ) : null}
      </CaptureWindow>
    </AbsoluteFill>
  );
};
