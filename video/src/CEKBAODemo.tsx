import React from "react";
import { AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import { C, SCENES, SceneId } from "./theme";
import { VO } from "./generated/timeline";
import { Captions } from "./components/Captions";
import { Evidence, Hook, Mechanism, Reveal, RootCause } from "./scenes/Explainer";
import { DemoA, DemoB, DemoC } from "./scenes/Demos";
import { Close, Security, Tests } from "./scenes/Proof";

const SCENE_COMPONENTS: Record<SceneId, React.FC> = {
  hook: Hook, mechanism: Mechanism, evidence: Evidence, root: RootCause, reveal: Reveal,
  demoA: DemoA, demoB: DemoB, demoC: DemoC, security: Security, tests: Tests, close: Close,
};

/** Short fade between scenes. The final scene holds its last frame (no fade-out). */
const SceneFade: React.FC<{ children: React.ReactNode; last: boolean }> = ({ children, last }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const inO = interpolate(frame, [0, 0.4 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const outO = last ? 1 : interpolate(frame, [durationInFrames - 0.3 * fps, durationInFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ opacity: inO * outO }}>{children}</AbsoluteFill>;
};

export const CEKBAODemo: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      {SCENES.map((s, i) => {
        const Scene = SCENE_COMPONENTS[s.id];
        return (
          <Sequence key={s.id} name={s.title} from={Math.round(s.start * fps)} durationInFrames={Math.round((s.end - s.start) * fps)}>
            <SceneFade last={i === SCENES.length - 1}><Scene /></SceneFade>
          </Sequence>
        );
      })}
      {VO.map((v) => (
        <Sequence key={v.id} name={`VO ${v.id}`} from={Math.round(v.start * fps)} durationInFrames={Math.ceil((v.end - v.start) * fps) + 6} layout="none">
          <Audio src={staticFile(v.file)} volume={1} />
        </Sequence>
      ))}
      <Audio src={staticFile("audio/music_bed.wav")} volume={0.07} />
      <Captions />
    </AbsoluteFill>
  );
};
