import { Audio } from "@remotion/media";
import { AbsoluteFill, Sequence, staticFile, useCurrentFrame } from "remotion";
import { Backdrop } from "./components/Backdrop.tsx";
import { Captions } from "./components/Captions.tsx";
import { Progress } from "./components/Chrome.tsx";
import { CaptureScene } from "./scenes/CaptureScene.tsx";
import { NvidiaScene, ResultsScene, type Facts } from "./scenes/Closing.tsx";
import { Intro } from "./scenes/Intro.tsx";
import { PolicyTimeline } from "./scenes/PolicyTimeline.tsx";
import { TitleCard } from "./scenes/TitleCard.tsx";
import { ACCENT, V } from "./theme.ts";
import type { Plan } from "./types.ts";

export type DemoProps = { plan: Plan | null };

export const DemoVideo: React.FC<DemoProps> = ({ plan }) => {
  const frame = useCurrentFrame();
  if (!plan) return <AbsoluteFill style={{ background: V.bg }} />;
  const f = plan.facts as unknown as Facts;
  const current = plan.scenes.find((s) => frame >= s.from && frame < s.from + s.durationInFrames) ?? plan.scenes[0];
  return (
    <AbsoluteFill style={{ background: V.bg }}>
      {plan.scenes.map((s) => {
        const accent = ACCENT[s.id] ?? [V.teal, V.violet];
        return (
          <Sequence key={s.id} from={s.from} durationInFrames={s.durationInFrames} name={s.id}>
            <Backdrop accent={accent} />
            {s.id === "intro" ? <Intro scene={s} preview={f.preview} /> : null}
            {s.card ? <TitleCard title={s.card.title} subtitle={s.card.subtitle} preview={f.preview} accent={accent} /> : null}
            {s.segments.length ? <CaptureScene scene={s} preview={f.preview} viewport={plan.viewport} accent={accent} /> : null}
            {s.id === "policy_timeline" ? <PolicyTimeline scene={s} preview={f.preview} /> : null}
            {s.id === "nvidia" ? <NvidiaScene f={f} scene={s} /> : null}
            {s.id === "results" ? <ResultsScene f={f} scene={s} /> : null}
          </Sequence>
        );
      })}
      {plan.audio.map((a, i) => (
        <Sequence key={`a${i}`} from={a.from} durationInFrames={a.durationInFrames} name={`narration ${i + 1}`}>
          <Audio src={staticFile(a.src)} />
        </Sequence>
      ))}
      {(plan.sfx ?? []).map((a, i) => (
        <Sequence key={`x${i}`} from={a.from} durationInFrames={a.durationInFrames} name={`sfx ${i + 1}`}>
          <Audio src={staticFile(a.src)} volume={a.volume} />
        </Sequence>
      ))}
      <Progress color={(ACCENT[current.id] ?? [V.teal])[0]} />
      <Captions cues={plan.captions} />
    </AbsoluteFill>
  );
};
