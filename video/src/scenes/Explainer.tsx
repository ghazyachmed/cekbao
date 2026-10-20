// Explanatory scenes (0:00-1:16). Line-drawn diagrams on black. Everything here
// is illustrative except the reported figures in <Evidence>, which carry their sources.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT } from "../theme";
import { fade, prog } from "../anim";
import { Box, Canvas, curve, Head, rr, Stroke, Txt } from "../components/Drawn";
import { Source, Tag } from "../components/Tag";

const useT = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps;
};

const circle = (cx: number, cy: number, r: number) => `M ${cx - r} ${cy} a ${r} ${r} 0 1 0 ${r * 2} 0 a ${r} ${r} 0 1 0 ${-r * 2} 0`;

/** Line-drawn student holding a phone. */
const Student: React.FC<{ t: number; t0: number; x: number; y: number }> = ({ t, t0, x, y }) => (
  <g>
    <Stroke d={circle(x, y, 46)} t={t} t0={t0} dur={0.8} w={3.5} />
    <Stroke d={`M ${x - 110} ${y + 230} C ${x - 105} ${y + 120}, ${x - 60} ${y + 70}, ${x} ${y + 70} C ${x + 60} ${y + 70}, ${x + 105} ${y + 120}, ${x + 110} ${y + 230}`} t={t} t0={t0 + 0.3} dur={0.9} w={3.5} />
    <Stroke d={`M ${x + 40} ${y + 150} C ${x + 70} ${y + 170}, ${x + 100} ${y + 150}, ${x + 120} ${y + 120}`} t={t} t0={t0 + 0.7} dur={0.6} w={3.5} />
    <Stroke d={rr(x + 105, y + 40, 62, 108, 12)} t={t} t0={t0 + 0.9} dur={0.7} w={3.5} />
  </g>
);

export const Hook: React.FC = () => {
  const t = useT();
  const dim = 1 - 0.72 * prog(t, 8.2, 9.0);
  const cardX = 700;
  const cardY = 280;
  const rowY = (i: number) => cardY + 92 + i * 74;
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Tag text="Illustrative · synthetic example" opacity={fade(t, 0.2)} />
      <Canvas>
        <g opacity={dim}>
          <Student t={t} t0={0.3} x={360} y={430} />
          <Stroke d={curve(480, 520, cardX - 10, 470, 0.5)} t={t} t0={1.2} dur={0.8} color={C.dim} w={2.5} />
          <Box x={cardX} y={cardY} w={1000} h={500} t={t} t0={1.0} r={20} />
          <Txt x={cardX + 50} y={rowY(0)} t={t} t0={1.6} size={30} color={C.dim} lines={["From   NBU Student Accounts"]} />
          <Txt x={cardX + 50} y={rowY(1)} t={t} t0={2.1} size={32} weight={700} lines={["Deposit overdue. Pay within 24 hours."]} />
          <Txt x={cardX + 50} y={rowY(2)} t={t} t0={2.6} size={30} lines={["Amount   USD 4,850.00"]} />
          <Txt x={cardX + 50} y={rowY(3)} t={t} t0={3.1} size={30} lines={["Beneficiary   NBU International Collections Ltd"]} />
        </g>
        {/* the changed detail stays in focus */}
        <Box x={cardX + 30} y={rowY(4) - 44} w={940} h={66} t={t} t0={5.4} color={C.coral} r={12} />
        <Txt x={cardX + 50} y={rowY(4)} t={t} t0={4.6} size={32} weight={700} color={C.coral} lines={["New bank account   ******9938 · SWIFT FKBKHKHH"]} />
        <Txt x={960} y={236} t={t} t0={8.4} size={104} weight={900} anchor="middle" lines={["Would you pay this?"]} />
      </Canvas>
    </AbsoluteFill>
  );
};

/** Line-drawn university building. */
const University: React.FC<{ t: number; t0: number; x: number; y: number }> = ({ t, t0, x, y }) => (
  <g>
    <Stroke d={`M ${x - 110} ${y - 40} L ${x} ${y - 110} L ${x + 110} ${y - 40} Z`} t={t} t0={t0} dur={0.8} w={3.5} />
    {[-80, -27, 27, 80].map((dx, i) => <Stroke key={i} d={`M ${x + dx} ${y - 30} V ${y + 70}`} t={t} t0={t0 + 0.4 + i * 0.1} dur={0.5} w={3.5} />)}
    <Stroke d={`M ${x - 125} ${y + 85} H ${x + 125}`} t={t} t0={t0 + 0.8} dur={0.5} w={3.5} />
  </g>
);

export const Mechanism: React.FC = () => {
  const t = useT();
  const nodeX = 1180;
  const dot = prog(t, 14.0, 16.4);
  // point along the lower route for the illustrative "money goes elsewhere" marker
  const bx = (p: number) => {
    const x1 = 540, y1 = 560, x2 = nodeX - 10, y2 = 740, dx = (x2 - x1) * 0.5;
    const u = 1 - p;
    return {
      x: u ** 3 * x1 + 3 * u * u * p * (x1 + dx) + 3 * u * p * p * (x2 - dx) + p ** 3 * x2,
      y: u ** 3 * y1 + 3 * u * u * p * y1 + 3 * u * p * p * y2 + p ** 3 * y2,
    };
  };
  const m = bx(dot);
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Tag text="Illustrative · synthetic example" opacity={fade(t, 0.2)} />
      <Canvas>
        <University t={t} t0={0.6} x={400} y={520} />
        <Txt x={400} y={660} t={t} t0={1.2} size={32} weight={700} anchor="middle" lines={["University"]} />
        {/* official route */}
        <Stroke d={curve(540, 480, nodeX - 10, 320, 0.5)} t={t} t0={1.8} dur={1.4} color={C.teal} w={4} />
        <Head x={nodeX - 10} y={320} t={t} t0={3.1} color={C.teal} />
        <Box x={nodeX} y={250} w={620} h={140} t={t} t0={3.0} color={C.teal} />
        <Txt x={nodeX + 36} y={312} t={t} t0={3.4} size={36} weight={800} color={C.teal} lines={["Official portal"]} />
        <Txt x={nodeX + 36} y={358} t={t} t0={3.7} size={28} color={C.line} lines={["Northbridge University"]} />
        {/* message-supplied route */}
        <Stroke d={curve(540, 560, nodeX - 10, 740, 0.5)} t={t} t0={7.0} dur={1.4} color={C.coral} w={4} />
        <Head x={nodeX - 10} y={740} t={t} t0={8.3} color={C.coral} />
        <Box x={nodeX} y={670} w={620} h={140} t={t} t0={8.2} color={C.coral} />
        <Txt x={nodeX + 36} y={732} t={t} t0={8.6} size={36} weight={800} color={C.coral} lines={["Account from the message"]} />
        <Txt x={nodeX + 36} y={778} t={t} t0={8.9} size={28} color={C.line} lines={["NBU International Collections Ltd"]} />
        {/* small envelope on the lower route */}
        <Stroke d={rr(800, 600, 86, 58, 6)} t={t} t0={7.4} dur={0.6} w={3} color={C.line} />
        <Stroke d="M 800 606 L 843 636 L 886 606" t={t} t0={7.8} dur={0.5} w={3} color={C.line} />
        {/* mismatch */}
        <Txt x={nodeX + 310} y={560} t={t} t0={12.4} size={64} weight={900} color={C.coral} anchor="middle" lines={["≠"]} />
        <Txt x={nodeX + 310} y={612} t={t} t0={12.8} size={28} color={C.dim} anchor="middle" lines={["different beneficiary"]} />
        {dot > 0 && dot < 1 ? <circle cx={m.x} cy={m.y} r={9} fill={C.coral} /> : null}
      </Canvas>
    </AbsoluteFill>
  );
};

const Card: React.FC<{ t: number; t0: number; x: number; place: string; big: string; line1: string; line2: string; line3: string; source: string }> = ({ t, t0, x, place, big, line1, line2, line3, source }) => {
  const o = fade(t, t0 + 0.2, 0.5);
  return (
    <>
      <Canvas><Box x={x} y={210} w={800} h={580} t={t} t0={t0} r={22} /></Canvas>
      <div style={{ position: "absolute", left: x + 50, top: 250, width: 700, fontFamily: FONT, color: C.line, opacity: o }}>
        <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: 3, color: C.dim, textTransform: "uppercase" }}>{place}</div>
        <div style={{ fontSize: 132, fontWeight: 900, lineHeight: 1.05, marginTop: 10 }}>{big}</div>
        <div style={{ fontSize: 34, fontWeight: 700, marginTop: 6, lineHeight: 1.25 }}>{line1}</div>
        <div style={{ fontSize: 28, color: C.dim, marginTop: 16, lineHeight: 1.35 }}>{line2}</div>
        <div style={{ fontSize: 28, color: C.gold, marginTop: 14, lineHeight: 1.35 }}>{line3}</div>
      </div>
      <Source text={source} x={x + 50} y={716} w={720} opacity={o} />
    </>
  );
};

export const Evidence: React.FC = () => {
  const t = useT();
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Tag text="Reported evidence · two separate incidents" opacity={fade(t, 0.2)} />
      <Card t={t} t0={0.5} x={120} place="Indonesia · 2025" big="273"
        line1="UMTS students reportedly affected"
        line2="Universitas Muhammadiyah Tapanuli Selatan, Padangsidimpuan. Campus figures, reported Feb 2025."
        line3="Campus check: 28 payment slips, only 6 matching bank transactions."
        source="Sources: detikSumut, 23 Feb 2025 · Kompas.com, 24 Feb 2025" />
      <Card t={t} t0={9.8} x={1000} place="Singapore · since March 2026" big="20+"
        line1="education-impersonation cases reported"
        line2="Fake school e-mails demanded urgent fee transfers. Victims are not described as international students."
        line3="Losses of at least S$31,000."
        source="Source: Singapore Police Force advisory, 19 Mar 2026" />
      <Source text="Figures as reported by each source. Not combined, not a prevalence rate." x={120} y={812} opacity={fade(t, 12.0)} />
    </AbsoluteFill>
  );
};

/** Slip, bank record and ledger icons for the root-cause diagram. */
const Slip: React.FC<{ t: number; t0: number; x: number; y: number }> = ({ t, t0, x, y }) => (
  <g>
    <Stroke d={`M ${x} ${y} H ${x + 150} V ${y + 190} l -15 12 l -15 -12 l -15 12 l -15 -12 l -15 12 l -15 -12 l -15 12 l -15 -12 l -15 12 l -15 -12 Z`} t={t} t0={t0} dur={1.0} w={3.5} />
    {[40, 75, 110, 145].map((dy, i) => <Stroke key={i} d={`M ${x + 25} ${y + dy} H ${x + (i === 3 ? 90 : 125)}`} t={t} t0={t0 + 0.6 + i * 0.12} dur={0.4} w={3} color={C.dim} />)}
  </g>
);
const Bank: React.FC<{ t: number; t0: number; x: number; y: number }> = ({ t, t0, x, y }) => (
  <g>
    <Stroke d={rr(x, y + 10, 170, 180, 14)} t={t} t0={t0} dur={0.9} w={3.5} />
    {[50, 90, 130].map((dy, i) => <Stroke key={i} d={`M ${x + 25} ${y + dy} H ${x + 145}`} t={t} t0={t0 + 0.5 + i * 0.12} dur={0.4} w={3} color={C.dim} />)}
  </g>
);
const Ledger: React.FC<{ t: number; t0: number; x: number; y: number; color: string }> = ({ t, t0, x, y, color }) => (
  <g>
    <Stroke d={rr(x, y, 190, 210, 14)} t={t} t0={t0} dur={0.9} w={3.5} color={color} />
    <Stroke d={`M ${x + 40} ${y} V ${y + 210}`} t={t} t0={t0 + 0.4} dur={0.5} w={3} color={color} />
    {[55, 100, 145].map((dy, i) => <Stroke key={i} d={`M ${x + 60} ${y + dy} H ${x + 165}`} t={t} t0={t0 + 0.6 + i * 0.1} dur={0.4} w={3} color={C.gold} dashed />)}
  </g>
);

export const RootCause: React.FC = () => {
  const t = useT();
  const confirm = prog(t, 10.4, 11.2);
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Tag text="Illustrative · synthetic example" opacity={fade(t, 0.2)} />
      <Canvas>
        <Txt x={960} y={250} t={t} t0={0.5} size={72} weight={900} anchor="middle" lines={["A receipt ≠ confirmed payment"]} />
        <Slip t={t} t0={1.0} x={320} y={360} />
        <Txt x={395} y={640} t={t} t0={1.6} size={32} weight={700} anchor="middle" lines={["Payment slip"]} />
        <Txt x={395} y={684} t={t} t0={1.9} size={28} color={C.dim} anchor="middle" lines={["the sender's claim"]} />
        <Stroke d={curve(500, 460, 860, 460, 0.4)} t={t} t0={3.8} dur={0.8} color={C.dim} w={3} />
        <Head x={860} y={460} t={t} t0={4.5} color={C.dim} />
        <Bank t={t} t0={4.2} x={880} y={360} />
        <Txt x={965} y={640} t={t} t0={4.8} size={32} weight={700} anchor="middle" lines={["Bank record"]} />
        <Txt x={965} y={684} t={t} t0={5.1} size={28} color={C.dim} anchor="middle" lines={["what left the account"]} />
        <Stroke d={curve(1070, 460, 1410, 460, 0.4)} t={t} t0={6.4} dur={0.8} color={C.gold} w={3} dashed />
        <Txt x={1240} y={430} t={t} t0={7.0} size={44} weight={900} color={C.gold} anchor="middle" lines={["?"]} />
        <Ledger t={t} t0={6.8} x={1430} y={350} color={confirm > 0.5 ? C.teal : C.line} />
        <Txt x={1525} y={640} t={t} t0={7.4} size={32} weight={700} anchor="middle" lines={["University ledger"]} />
        <Txt x={1525} y={684} t={t} t0={7.7} size={28} color={C.gold} anchor="middle" lines={["no matching record"]} out={10.6} />
        <Txt x={1525} y={684} t={t} t0={10.8} size={28} weight={700} color={C.teal} anchor="middle" lines={["only this confirms payment"]} />
      </Canvas>
    </AbsoluteFill>
  );
};

export const Reveal: React.FC = () => {
  const t = useT();
  const nodes = [
    { label: "Message", sub: "pasted by the student", t0: 4.2, color: C.line },
    { label: "Evidence check", sub: "registry, ledger, rules", t0: 5.6, color: C.line },
    { label: "HOLD or review", sub: "unverified items held", t0: 7.2, color: C.coral },
    { label: "Official next step", sub: "official contact, plan", t0: 8.8, color: C.teal },
  ];
  const nx = (i: number) => 140 + i * 420;
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Tag text="How CEKBAO works" opacity={fade(t, 0.2)} />
      <Canvas>
        <Txt x={960} y={330} t={t} t0={0.3} size={128} weight={900} anchor="middle" spacing={8} lines={["CEKBAO"]} />
        <Txt x={960} y={410} t={t} t0={1.0} size={40} anchor="middle" color={C.teal} italic lines={["Check the request. Use the official route."]} />
        {nodes.map((n, i) => (
          <g key={i}>
            <Box x={nx(i)} y={540} w={380} h={150} t={t} t0={n.t0} color={n.color} />
            <Txt x={nx(i) + 190} y={605} t={t} t0={n.t0 + 0.3} size={32} weight={800} anchor="middle" color={n.color} lines={[n.label]} />
            <Txt x={nx(i) + 190} y={650} t={t} t0={n.t0 + 0.5} size={26} anchor="middle" color={C.dim} lines={[n.sub]} />
            {i < 3 ? (
              <>
                <Stroke d={`M ${nx(i) + 390} 615 H ${nx(i + 1) - 12}`} t={t} t0={nodes[i + 1].t0 - 0.4} dur={0.4} w={3} color={C.dim} />
                <Head x={nx(i + 1) - 10} y={615} t={t} t0={nodes[i + 1].t0 - 0.05} color={C.dim} />
              </>
            ) : null}
          </g>
        ))}
      </Canvas>
    </AbsoluteFill>
  );
};
