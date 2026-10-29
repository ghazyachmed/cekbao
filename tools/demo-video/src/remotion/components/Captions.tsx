import { useCurrentFrame, useVideoConfig } from "remotion";
import type { Cue } from "../types.ts";
import { C, FONT, L } from "../theme.ts";

// Burned-in captions: same cues as the exported SRT and JSON, 46 px, max two lines, in a band below the app frame.
// A dark plate keeps the contrast fixed over the moving colour glows.
export const Captions: React.FC<{ cues: Cue[] }> = ({ cues }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const cue = cues.find((c) => t >= c.start && t < c.end);
  if (!cue) return null;
  return (
    <div style={{ position: "absolute", left: L.safeX, right: L.safeX, top: L.captionTop,
                  height: L.captionBottom - L.captionTop, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ fontFamily: FONT, fontSize: 46, lineHeight: "56px", fontWeight: 600, color: C.text, textAlign: "center",
                    background: "rgba(6,11,24,0.78)", borderRadius: 16, padding: "4px 26px" }}>
        {cue.lines.map((l, i) => <div key={i}>{l}</div>)}
      </div>
    </div>
  );
};
