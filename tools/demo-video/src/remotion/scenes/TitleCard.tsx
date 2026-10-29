import { useCurrentFrame, useVideoConfig } from "remotion";
import { Header } from "../components/Chrome.tsx";
import { pop, prog } from "../motion.ts";
import { C, FONT, L, V } from "../theme.ts";

// Kinetic title card between scenarios: the scenario letter springs in, the title rises word by word,
// and an accent bar sweeps under it.
export const TitleCard: React.FC<{ title: string; subtitle: string; preview: boolean; accent: [string, string] }> =
  ({ title, subtitle, preview, accent }) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();
    const letter = subtitle.match(/Scenario (\w)/)?.[1] ?? "";
    const label = subtitle.replace(/^Scenario \w:\s*/, "");
    const disc = pop(frame, 0, fps, 9);
    return (
      <>
        <Header left="CEKBAO: payment instruction check" preview={preview} accent={accent[0]} />
        <div style={{ position: "absolute", left: L.frameX - 40, top: 330, display: "flex", gap: 56, alignItems: "flex-start",
                      fontFamily: FONT }}>
          <div style={{ width: 210, height: 210, borderRadius: 999, flex: "none", display: "grid", placeItems: "center",
                        background: `linear-gradient(140deg, ${accent[0]}, ${accent[1]})`, color: V.ink, fontSize: 132,
                        fontWeight: 900, boxShadow: `0 0 90px ${accent[0]}88`, scale: String(disc),
                        rotate: `${(1 - disc) * -40}deg` }}>{letter}</div>
          <div style={{ paddingTop: 18, maxWidth: 1180 }}>
            <div style={{ fontSize: 36, fontWeight: 700, color: accent[0], marginBottom: 18, opacity: prog(frame, 4, 10),
                          translate: `${(1 - prog(frame, 4, 14)) * -40}px 0px`, letterSpacing: "0.01em" }}>
              {letter ? `Scenario ${letter} · ${label}` : subtitle}
            </div>
            <div style={{ fontSize: 72, lineHeight: "84px", fontWeight: 850, color: C.text, letterSpacing: "-0.015em" }}>
              {title.split(" ").map((w, i) => {
                const p = prog(frame, 8 + i * 2.5, 14);
                return <span key={i} style={{ display: "inline-block", marginRight: 20, opacity: p,
                                              translate: `0px ${(1 - p) * 46}px` }}>{w}</span>;
              })}
            </div>
            <div style={{ height: 10, borderRadius: 99, marginTop: 26, width: 520 * prog(frame, 14, 20),
                          background: `linear-gradient(90deg, ${accent[0]}, ${accent[1]})` }} />
          </div>
        </div>
      </>
    );
  };
