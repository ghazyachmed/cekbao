// Security controls, re-run test evidence, limits and close.
import React from "react";
import { AbsoluteFill, Img, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import { apiResult } from "../captures";
import { EVIDENCE } from "../generated/evidence";
import { C, COMMIT, COMMIT_NOTE, FONT, MONO, REPO_URL } from "../theme";
import { fade, prog } from "../anim";
import { Box, Canvas, curve, Stroke, Txt } from "../components/Drawn";
import { Source, Tag } from "../components/Tag";

const useT = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps;
};

const short = (body: string) => {
  try {
    const d = JSON.parse(body).detail as string;
    return d.length > 46 ? d.slice(0, 45) + "…" : d;
  } catch {
    return body.slice(0, 46);
  }
};

export const Security: React.FC = () => {
  const t = useT();
  const { fps } = useVideoConfig();
  const roles = [
    { label: "Anonymous", y: 250, t0: 3.8, api: apiResult("No session"), what: "no session" },
    { label: "Student", y: 390, t0: 6.0, api: apiResult("Ayu opens Citra"), what: "another student's case" },
    { label: "Office reviewer", y: 530, t0: 8.6, api: apiResult("Office reviewer tries"), what: "approve a student's plan" },
  ];
  const panel = prog(t, 13.0, 13.6);
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Tag text="Real HTTP responses · captured 2026-10-20" opacity={fade(t, 0.2)} />
      <Canvas>
        <g opacity={1 - 0.8 * panel}>
          <Box x={760} y={380} w={360} h={140} t={t} t0={0.6} color={C.teal} />
          <Txt x={940} y={442} t={t} t0={0.9} size={34} weight={800} anchor="middle" color={C.teal} lines={["Server policy"]} />
          <Txt x={940} y={484} t={t} t0={1.1} size={26} anchor="middle" color={C.dim} lines={["roles, owner, CSRF"]} />
          {roles.map((r, i) => (
            <g key={i}>
              <Box x={120} y={r.y} w={420} h={100} t={t} t0={r.t0} />
              <Txt x={330} y={r.y + 62} t={t} t0={r.t0 + 0.2} size={32} weight={700} anchor="middle" lines={[r.label]} />
              <Stroke d={curve(540, r.y + 50, 760, 450, 0.5)} t={t} t0={r.t0 + 0.3} dur={0.6} color={C.dim} w={2.5} />
              <Stroke d={curve(1120, 450, 1240, r.y + 50, 0.5)} t={t} t0={r.t0 + 0.7} dur={0.5} color={C.coral} w={2.5} />
            </g>
          ))}
          <Box x={120} y={670} w={420} h={100} t={t} t0={19.0} color={C.gold} dashed />
          <Txt x={330} y={732} t={t} t0={19.2} size={32} weight={700} anchor="middle" color={C.gold} lines={["Optional LLM"]} />
        </g>
      </Canvas>
      {roles.map((r, i) => {
        const o = fade(t, r.t0 + 0.9, 0.4) * (1 - 0.8 * panel);
        return (
          <div key={i} style={{ position: "absolute", left: 1250, top: r.y + 8, width: 550, opacity: o, fontFamily: MONO, fontSize: 24, color: C.line, lineHeight: 1.4 }}>
            <span style={{ color: C.coral, fontWeight: 700, fontSize: 30 }}>{r.api.status}</span>
            <span style={{ fontFamily: FONT, color: C.dim, fontSize: 26 }}>  {r.what}</span>
            <div style={{ color: C.dim }}>{short(r.api.body)}</div>
          </div>
        );
      })}
      {roles.map((r, i) => (
        <Sequence key={i} from={Math.round((r.t0 + 0.9) * fps)} durationInFrames={12} layout="none">
          <Audio src={staticFile("audio/sfx_click.wav")} volume={0.3} />
        </Sequence>
      ))}
      {panel > 0 ? (
        <div style={{ position: "absolute", left: 600, top: 180, width: 1200, opacity: panel }}>
          <div style={{ fontFamily: FONT, fontSize: 30, fontWeight: 800, color: C.coral, marginBottom: 14 }}>Hidden instructions in a message → payment held</div>
          <div style={{ width: 1200, height: 420, overflow: "hidden", borderRadius: 16, border: `1.5px solid ${C.faint}`, position: "relative" }}>
            <Img src={staticFile("captures/D2_injection_hold.png")} style={{ position: "absolute", left: -408 * 1.087 + 0, top: -10, width: 1920 * 1.087, maxWidth: "none" }} />
          </div>
          <div style={{ fontFamily: FONT, fontSize: 24, color: C.dim, marginTop: 10 }}>Real capture of the sandbox app. The e-mail matches the registry, but its embedded instructions keep the decision at HOLD_DO_NOT_PAY.</div>
        </div>
      ) : null}
      {t > 19.0 ? (
        <div style={{ position: "absolute", left: 600, top: 760, width: 1200, opacity: fade(t, 19.2, 0.4), fontFamily: FONT, fontSize: 28, fontWeight: 700, color: C.gold }}>
          Optional LLM adapter: tested with a mock provider only. No live model run.
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

export const Tests: React.FC = () => {
  const t = useT();
  // Function names exactly as printed by pytest; the file prefix is dropped to fit the panel.
  const lines = EVIDENCE.testLines.map((l) => l.replace(/^tests\/[^:]+::/, "").replace(/\[.*\]/, "[look-alike link]"));
  const shown = Math.floor(interp(t, 0.8, 5.6, 0, lines.length));
  const n117 = Math.round(interp(t, 5.6, 6.8, 0, EVIDENCE.passed));
  const limits = [
    "Synthetic, team-authored test cases",
    "No independent accuracy study",
    "Optional LLM: mock-tested only",
    "No bank connection. No money moved.",
  ];
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Tag text={`Re-run today · commit ${COMMIT}`} opacity={fade(t, 0.2)} />
      <div style={{ position: "absolute", left: 120, top: 170, width: 1060, height: 620, borderRadius: 16, border: `1.5px solid ${C.faint}`, background: C.panel, padding: "22px 26px", fontFamily: MONO, fontSize: 22, lineHeight: 1.5, color: C.line, overflow: "hidden" }}>
        <div style={{ color: C.dim }}>$ .venv/bin/python -m pytest -v</div>
        {lines.slice(0, shown).map((l, i) => (
          <div key={i} style={{ whiteSpace: "nowrap" }}>{l.replace(" PASSED", "")} <span style={{ color: C.teal }}>PASSED</span></div>
        ))}
        {t > 5.6 ? <div style={{ color: C.teal, fontWeight: 700, opacity: fade(t, 5.6, 0.3) }}>{EVIDENCE.summary} · {EVIDENCE.pytestExit}</div> : null}
        {t > 6.6 ? <div style={{ color: C.dim, marginTop: 8, opacity: fade(t, 6.6, 0.3) }}>$ .venv/bin/python scripts/run_scenarios.py</div> : null}
        {t > 7.2 ? <div style={{ color: C.teal, fontWeight: 700, opacity: fade(t, 7.2, 0.3), whiteSpace: "normal" }}>{EVIDENCE.scenSummary.split(". Mode")[0]} · {EVIDENCE.scenExit}</div> : null}
      </div>
      <div style={{ position: "absolute", left: 1240, top: 170, width: 560, fontFamily: FONT, color: C.line }}>
        <div style={{ opacity: fade(t, 5.6, 0.4) }}>
          <div style={{ fontSize: 120, fontWeight: 900, lineHeight: 1 }}>{n117}</div>
          <div style={{ fontSize: 30, color: C.dim }}>tests passed (re-run today)</div>
        </div>
        <div style={{ opacity: fade(t, 7.2, 0.4), marginTop: 26 }}>
          <div style={{ fontSize: 96, fontWeight: 900, lineHeight: 1 }}>{EVIDENCE.scenPassed}/{EVIDENCE.scenTotal}</div>
          <div style={{ fontSize: 30, color: C.dim }}>sandbox scenario assertions</div>
        </div>
        <div style={{ marginTop: 30 }}>
          {limits.map((l, i) => (
            <div key={i} style={{ opacity: fade(t, 9.6 + i * 0.8, 0.4), fontSize: 28, color: C.gold, marginTop: 10, display: "flex", gap: 12 }}>
              <span>•</span><span>{l}</span>
            </div>
          ))}
        </div>
      </div>
      <Source text={`Outputs from this checkout on 2026-10-20 (${COMMIT}, ${COMMIT_NOTE}). Recorded results, not independent validation.`} x={120} y={808} opacity={fade(t, 1.0)} />
    </AbsoluteFill>
  );
};

function interp(t: number, t0: number, t1: number, a: number, b: number) {
  return a + (b - a) * prog(t, t0, t1, (x) => x);
}

export const Close: React.FC = () => {
  const t = useT();
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <Canvas>
        <Txt x={960} y={300} t={t} t0={0.2} size={136} weight={900} anchor="middle" spacing={8} lines={["CEKBAO"]} />
        <Txt x={960} y={380} t={t} t0={0.7} size={42} anchor="middle" italic color={C.teal} lines={["Check the request. Use the official route."]} />
        <Txt x={960} y={470} t={t} t0={1.4} size={34} weight={700} anchor="middle" lines={["HMIF · Institut Teknologi Bandung"]} />
        <Txt x={960} y={520} t={t} t0={1.8} size={30} anchor="middle" color={C.dim} lines={["2026 Shenzhen FinTechathon · International Track · Topic C"]} />
        <Txt x={960} y={590} t={t} t0={2.4} size={30} anchor="middle" lines={[`${REPO_URL} · commit ${COMMIT}`]} />
        <Stroke d="M 560 630 H 1360" t={t} t0={2.8} dur={0.8} color={C.faint} w={2} />
      </Canvas>
      <Source text="Sandbox prototype with synthetic data. No real payments, bank connections, partnerships or live LLM evaluation." x={260} y={660} w={1400} opacity={fade(t, 3.0)} />
      <Source text="Sources: Singapore Police Force advisory, 19 Mar 2026 · detikSumut, 23 Feb 2025 · Kompas.com, 24 Feb 2025" x={260} y={735} w={1400} opacity={fade(t, 3.4)} />
    </AbsoluteFill>
  );
};
