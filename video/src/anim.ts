import { Easing, interpolate } from "remotion";

const ease = Easing.bezier(0.16, 1, 0.3, 1);

/** 0 -> 1 between t0 and t1 (seconds), eased and clamped. */
export const prog = (t: number, t0: number, t1: number, easing = ease) =>
  interpolate(t, [t0, t1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing });

/** Fade in at t0 over d seconds; optional fade out ending at t2. */
export const fade = (t: number, t0: number, d = 0.5, t2?: number, d2 = 0.4) => {
  const a = prog(t, t0, t0 + d);
  return t2 === undefined ? a : a * (1 - prog(t, t2 - d2, t2));
};

export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
