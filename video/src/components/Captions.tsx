// Burned-in English captions. Source of truth: the generated SRT, parsed with
// @remotion/captions so the on-screen text and the exported .srt cannot drift.
import React from "react";
import { parseSrt } from "@remotion/captions";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { CAPTIONS_SRT } from "../generated/timeline";
import { C, FONT } from "../theme";

const { captions } = parseSrt({ input: CAPTIONS_SRT });

export const Captions: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ms = (frame / fps) * 1000;
  const cue = captions.find((c) => ms >= c.startMs && ms < c.endMs);
  if (!cue) return null;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 100, display: "flex", justifyContent: "center", pointerEvents: "none" }}>
      <div style={{
        maxWidth: 1480, padding: "10px 26px", borderRadius: 12, background: "rgba(7, 11, 16, 0.88)",
        color: C.line, fontFamily: FONT, fontWeight: 700, fontSize: 40, lineHeight: 1.3, textAlign: "center",
        whiteSpace: "pre-line", border: `1px solid ${C.faint}`,
      }}>
        {cue.text.trim()}
      </div>
    </div>
  );
};
