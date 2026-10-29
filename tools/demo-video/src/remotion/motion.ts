// Frame-driven motion helpers (no CSS transitions: Remotion renders each frame independently).
import { Easing, interpolate, spring } from "remotion";

export const ease = Easing.bezier(0.16, 1, 0.3, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** 0 -> 1 from frame `at` over `dur` frames, eased. */
export const prog = (frame: number, at: number, dur: number, easing = ease) =>
  interpolate(frame, [at, at + dur], [0, 1], { ...clamp, easing });

/** Springy 0 -> 1 (slight overshoot) starting at frame `at`. */
export const pop = (frame: number, at: number, fps: number, damping = 12) =>
  spring({ frame: frame - at, fps, config: { damping, stiffness: 170, mass: 0.8 } });

/** Visible window: fades in at `from`, fades out before `to` (to = Infinity keeps it). */
export const windowed = (frame: number, from: number, to = Infinity, fadeIn = 8, fadeOut = 8) =>
  Math.min(prog(frame, from, fadeIn), to === Infinity ? 1 : 1 - prog(frame, to - fadeOut, fadeOut));

export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

/** Point on a quadratic Bezier curve (for objects that travel along a drawn path). */
export const onCurve = (p0: [number, number], c: [number, number], p1: [number, number], t: number): [number, number] => [
  (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
  (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1],
];
