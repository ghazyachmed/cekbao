import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { V } from "../theme.ts";

// Animated stage: two slow-drifting colour glows over a dot grid. Gradients only (no CSS blur) to keep renders fast.
export const Backdrop: React.FC<{ accent: [string, string] }> = ({ accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const glow = (color: string, x: number, y: number, r: number) =>
    `radial-gradient(circle ${r}px at ${x}px ${y}px, ${color}55 0%, ${color}22 45%, transparent 100%)`;
  return (
    <AbsoluteFill style={{ background: V.bg }}>
      <AbsoluteFill style={{ background: [
        glow(accent[0], 360 + Math.sin(t * 0.35) * 160, 260 + Math.cos(t * 0.27) * 90, 760),
        glow(accent[1], 1580 + Math.cos(t * 0.3) * 150, 820 + Math.sin(t * 0.4) * 80, 820),
      ].join(", ") }} />
      <AbsoluteFill style={{ backgroundImage: "radial-gradient(rgba(255,255,255,0.09) 1.5px, transparent 1.6px)",
                             backgroundSize: "36px 36px", backgroundPosition: `${(t * 6) % 36}px 0px` }} />
    </AbsoluteFill>
  );
};
