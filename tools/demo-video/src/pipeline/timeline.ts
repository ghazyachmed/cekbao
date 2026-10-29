// Scene timing for the composition. A scene lasts as long as its capture or its narration, whichever is longer,
// so sentences are never cut to hit a target.
export type SceneSpec = { id: string; videoSeconds: number; narrationSeconds: number; padSeconds: number };
export type TimedScene = { id: string; from: number; durationInFrames: number };

export function buildTimeline(specs: SceneSpec[], fps: number): { scenes: TimedScene[]; totalFrames: number } {
  let from = 0;
  const scenes = specs.map((s) => {
    const seconds = Math.max(s.videoSeconds, s.narrationSeconds + s.padSeconds);
    const durationInFrames = Math.ceil(seconds * fps);
    const scene = { id: s.id, from, durationInFrames };
    from += durationInFrames;
    return scene;
  });
  return { scenes, totalFrames: from };
}

export function checkDuration(totalSeconds: number, target: number, limit: number | null) {
  return { totalSeconds, target, limit, withinLimit: limit === null || totalSeconds <= limit,
           deviationFromTargetSeconds: Math.round((totalSeconds - target) * 10) / 10 };
}
