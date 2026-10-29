import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { PlannedScene } from "../types.ts";
import { Header, Logo } from "../components/Chrome.tsx";
import { pop, prog } from "../motion.ts";
import { C, FONT, L, TONE, V } from "../theme.ts";

export type Facts = { preview: boolean; mode: string; modelId: string | null; latencyMs: number | null; tokens: string | null;
  checkedAt: string | null; license: string; testsPassed: number | null; axeViolations: number | null;
  lighthouseA11y: number | null; decisions: [string, string][]; repo: string; blockedReason: string | null };

const Title: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: L.safeX, top: 120, fontFamily: FONT, fontSize: 64, fontWeight: 900,
                  color: C.text, letterSpacing: "-0.015em", opacity: prog(frame, 0, 10),
                  translate: `0px ${(1 - prog(frame, 0, 16)) * 30}px` }}>{children}</div>
  );
};

// NVIDIA through Nebius: the integration evidence card comes from the evidence manifest, not from configuration.
// The pipeline builds step by step; a pulse runs down it. The model step is dashed and stamped when it was not called.
export const NvidiaScene: React.FC<{ f: Facts; scene: PlannedScene }> = ({ f, scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const beats = scene.beats ?? [18, 120, 240];
  const live = f.mode === "live" || f.mode === "replay";
  const rows: [string, string][] = [
    ["Provider", "Nebius Token Factory"],
    ["Model", f.modelId ?? "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"],
    ["Licence", "NVIDIA Nemotron Open Model License (open weights, not OSI open source)"],
    ["This video", live ? (f.mode === "replay" ? `Recorded inference, ${((f.latencyMs ?? 0) / 1000).toFixed(1)} s`
                                              : `Live call, ${((f.latencyMs ?? 0) / 1000).toFixed(1)} s measured`)
                        : "Not called: no API key or budget configured"],
  ];
  const steps = ["Instruction saved (202 after commit)", "Worker leases the job",
                 "NVIDIA Nemotron proposes fields with quotes", "Code checks every quote", "Rules: policy valid on the date"];
  const STEP_H = 82, GAP = 26;
  const pulseY = ((frame - beats[0]) % 75) / 75 * (steps.length * (STEP_H + GAP) - GAP);
  const stamp = pop(frame, beats[1] + 6, fps, 8);
  return (
    <>
      <Header left="NVIDIA model through Nebius" preview={f.preview} accent={V.green} />
      <Title>Integration <span style={{ color: V.green }}>status</span></Title>
      <div style={{ position: "absolute", left: L.safeX, top: 240, width: 900, background: "#fff", color: V.ink, borderRadius: 22,
                    padding: 32, fontFamily: FONT, boxShadow: `0 0 0 4px ${V.green}, 0 0 70px ${V.green}44`,
                    scale: String(interpolate(pop(frame, 4, fps, 14), [0, 1], [0.85, 1])), opacity: prog(frame, 4, 8) }}>
        <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
          <span style={{ fontSize: 30, fontWeight: 800 }}>Evidence from this recording</span>
          <span style={{ flex: 1 }} />
          <span style={{ background: live ? V.teal : V.coral, color: V.ink, borderRadius: 999, padding: "4px 18px",
                         fontSize: 26, fontWeight: 900, scale: String(stamp), display: "inline-block" }}>
            {live ? (f.mode === "replay" ? "RECORDED" : "LIVE") : "NOT CALLED"}</span>
        </div>
        {rows.map(([k, v], i) => (
          <div key={k} style={{ display: "flex", gap: 20, padding: "12px 0", borderTop: "2px solid #dfe6ee",
                                opacity: prog(frame, 10 + i * 6, 10), translate: `${(1 - prog(frame, 10 + i * 6, 14)) * 30}px 0px` }}>
            <div style={{ width: 170, fontSize: 28, fontWeight: 700, color: "#3c4d5e" }}>{k}</div>
            <div style={{ flex: 1, fontSize: 28, lineHeight: "38px", wordBreak: "break-word" }}>{v}</div>
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 1060, top: 240, width: 764, fontFamily: FONT }}>
        <div style={{ position: "absolute", left: 38, top: 0, width: 6, height: steps.length * (STEP_H + GAP) - GAP,
                      background: "rgba(255,255,255,0.18)", borderRadius: 99 }} />
        {frame > beats[0] + 20 ? <div style={{ position: "absolute", left: 29, top: pulseY - 12, width: 24, height: 24,
                                               borderRadius: 99, background: V.teal, boxShadow: `0 0 30px ${V.teal}` }} /> : null}
        {steps.map((s, i) => {
          const model = i === 2;
          const p = pop(frame, beats[0] + i * 8, fps, 13);
          const color = model ? V.green : [V.blue, V.violet, V.green, V.amber, V.teal][i];
          return (
            <div key={s} style={{ position: "relative", height: STEP_H, marginBottom: GAP, display: "flex", alignItems: "center",
                                  gap: 18, padding: "0 22px", borderRadius: 16, fontSize: 30, fontWeight: model ? 800 : 650,
                                  color: C.text, background: model ? "rgba(118,185,0,.16)" : "rgba(15,26,49,0.92)",
                                  border: `3px ${model && !live ? "dashed" : "solid"} ${color}`,
                                  scale: String(interpolate(p, [0, 1], [0.7, 1])), opacity: Math.min(1, p * 2),
                                  transformOrigin: "0% 50%" }}>
              <span style={{ width: 36, height: 36, borderRadius: 99, background: color, flex: "none" }} />
              {s}
              {model && !live ? (
                <span style={{ position: "absolute", right: -18, top: -22, background: V.coral, color: V.ink, borderRadius: 10,
                               padding: "2px 12px", fontSize: 24, fontWeight: 900, rotate: "6deg", scale: String(stamp) }}>
                  not called</span>
              ) : null}
            </div>
          );
        })}
      </div>
    </>
  );
};

// Measured results, limits and the project link (only measured numbers; no invented outcomes).
export const ResultsScene: React.FC<{ f: Facts; scene: PlannedScene }> = ({ f, scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const beats = scene.beats ?? [18, 150, 280, 400];
  const tests = Math.round(interpolate(frame, [beats[0], beats[0] + 36], [0, f.testsPassed ?? 0],
                                       { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const tiles: [string, string, string][] = [
    [String(tests), "automated tests pass", V.teal],
    [String(f.axeViolations ?? "?"), "axe-core WCAG violations on audited pages", V.blue],
  ];
  const limits = ["Synthetic institutions and accounts", "No user testing yet",
                  ...(f.mode === "live" || f.mode === "replay" ? [] : ["No live model call in this preview"]),
                  "Not a payment or settlement check"];
  const toneOf = (d: string) => (/^conflict/i.test(d) ? TONE.bad : /^match/i.test(d) ? TONE.ok : TONE.warn);
  return (
    <>
      <Header left="Results and limits" preview={f.preview} accent={V.teal} />
      <Title>What was <span style={{ color: V.teal }}>measured</span></Title>
      <div style={{ position: "absolute", left: L.safeX, top: 240, width: 1000, fontFamily: FONT, color: C.text }}>
        <div style={{ display: "flex", gap: 24 }}>
          {tiles.map(([n, label, color], i) => {
            const p = pop(frame, beats[0] + i * 8, fps, 12);
            return (
              <div key={label} style={{ flex: 1, padding: "18px 26px", borderRadius: 20, background: "rgba(15,26,49,0.92)",
                                        border: `4px solid ${color}`, boxShadow: `0 0 50px ${color}44`, scale: String(p) }}>
                <div style={{ fontSize: 88, lineHeight: "96px", fontWeight: 900, color, fontVariantNumeric: "tabular-nums" }}>{n}</div>
                <div style={{ fontSize: 28, fontWeight: 700 }}>{label}</div>
              </div>
            );
          })}
        </div>
        {f.decisions.map(([s, d], i) => {
          const t = toneOf(d);
          const p = prog(frame, beats[0] + 24 + i * 8, 12);
          return (
            <div key={s} style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 18, fontSize: 28, lineHeight: "36px",
                                  fontWeight: 650, opacity: p, translate: `${(1 - p) * 40}px 0px` }}>
              <span style={{ width: 52, height: 52, borderRadius: 99, flex: "none", background: t.color, color: V.ink,
                             display: "grid", placeItems: "center", fontSize: 28, fontWeight: 900 }}>{s}</span>
              {d}
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 1170, top: 240, width: 654, fontFamily: FONT, color: C.text }}>
        <div style={{ fontSize: 34, fontWeight: 900, color: V.amber, marginBottom: 8, opacity: prog(frame, beats[1], 10) }}>Limits</div>
        {limits.map((m, i) => {
          const p = prog(frame, beats[1] + 4 + i * 6, 12);
          return (
            <div key={m} style={{ display: "flex", gap: 14, alignItems: "center", fontSize: 30, lineHeight: "40px", padding: "10px 0",
                                  borderTop: `2px solid ${C.line}`, opacity: p, translate: `${(1 - p) * 40}px 0px` }}>
              <span style={{ color: V.amber, fontWeight: 900 }}>!</span>{m}
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: L.safeX, right: L.safeX, top: 760, display: "flex", alignItems: "center", gap: 40,
                    fontFamily: FONT, opacity: prog(frame, beats[beats.length - 1], 12) }}>
        <Logo size={64} />
        <span style={{ fontSize: 36, color: C.text }}>Code: <span style={{ color: V.teal, fontWeight: 800 }}>
          {f.repo.slice(0, Math.round(f.repo.length * prog(frame, beats[beats.length - 1] + 4, 30, (x) => x)))}</span></span>
      </div>
    </>
  );
};
