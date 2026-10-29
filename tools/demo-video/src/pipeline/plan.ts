// Composition plan: captures + voiced narration -> frame-exact props for Remotion (the structured timeline).
import type { ScenarioCapture } from "./capture.ts";
import { splitIntoCues, type Cue } from "./captions.ts";
import type { Callout, NarrationLine } from "./narration.ts";
import { buildTimeline } from "./timeline.ts";
import type { Voiced } from "./tts.ts";

export const CAPTURE_SCENES = ["conflict", "policy_change", "insufficient", "escalation"];
export const TITLE_CARDS: Record<string, { title: string; subtitle: string; seconds: number }> = {
  title_conflict: { title: "Does this payment instruction match the policy?", subtitle: "Scenario A: a new payee and account", seconds: 2.6 },
  title_policy_change: { title: "Same details, different date", subtitle: "Scenario B: the policy changed on 1 September", seconds: 2.0 },
  title_insufficient: { title: "Who authorized this source?", subtitle: "Scenario C: a publisher without authority", seconds: 2.0 },
};
// The reviewer scene (escalation) is still captured but left out of the edit: judges watch at most three minutes.
export const SCENE_ORDER = ["intro", "title_conflict", "conflict", "title_policy_change", "policy_change", "policy_timeline",
                            "title_insufficient", "insufficient", "nvidia", "results"];
// Original synthesized sound effects (tools/demo-video/sfx/make_sfx.py): file, length in seconds and mix volume.
// Volumes keep the effects well under the narration so the measured narration levels stay comparable.
export const SFX = {
  whoosh: { src: "sfx/whoosh.wav", seconds: 0.7, volume: 0.32 },
  pop: { src: "sfx/pop.wav", seconds: 0.25, volume: 0.16 },
  click: { src: "sfx/click.wav", seconds: 0.12, volume: 0.22 },
};
export const CAPTION_CHARS = 44;
const GAP = 0.35;

export type Click = { frame: number; x: number; y: number };
export type Segment = { video: string; startFrom: number; playFrames: number; freezeFrames: number; from: number;
                        inset?: { src: string; width: number; height: number; delay: number }; label: string;
                        clicks: Click[]; callout?: Callout & { frames: number } };
export type Still = { src: string; width: number; height: number };
export type PlannedScene = { id: string; from: number; durationInFrames: number; segments: Segment[];
                             title?: string; code?: string; card?: { title: string; subtitle: string };
                             beats?: number[]; teaser?: Still; verdicts?: string[] };
export type AudioClip = { src: string; from: number; durationInFrames: number };
export type SfxClip = AudioClip & { volume: number };
export type Plan = { fps: number; width: number; height: number; viewport: { width: number; height: number };
                     totalFrames: number; footageFrames: number; productFrame: number; scenes: PlannedScene[];
                     audio: AudioClip[]; sfx: SfxClip[]; captions: Cue[]; facts: Record<string, unknown> };

export function makePlan(lines: NarrationLine[], voiced: Voiced[], captures: Record<string, ScenarioCapture>,
                         assetBase: string, fps: number, facts: Record<string, unknown>): Plan {
  const seconds = new Map(voiced.map((v) => [v.id, v]));
  const f = (s: number) => Math.round(s * fps);
  const specs: { id: string; videoSeconds: number; narrationSeconds: number; padSeconds: number }[] = [];
  const sceneSegments = new Map<string, Segment[]>();
  const lineOffsets = new Map<string, number>();

  for (const id of SCENE_ORDER) {
    if (TITLE_CARDS[id]) { specs.push({ id, videoSeconds: TITLE_CARDS[id].seconds, narrationSeconds: 0, padSeconds: 0 }); continue; }
    const sceneLines = lines.filter((l) => l.scene === id);
    if (!CAPTURE_SCENES.includes(id)) {
      let t = 0.6;
      for (const l of sceneLines) { lineOffsets.set(l.id, t); t += seconds.get(l.id)!.seconds + GAP; }
      specs.push({ id, videoSeconds: 0, narrationSeconds: t, padSeconds: 0.9 });
      continue;
    }
    const cap = captures[id];
    const mk = new Map(cap.markers.map((m) => [m.label, m.t]));
    const anchored = sceneLines.filter((l) => l.anchor && mk.has(l.anchor));
    if (anchored.length !== sceneLines.length) {
      const missing = sceneLines.filter((l) => !anchored.includes(l)).map((l) => l.anchor);
      throw new Error(`scene ${id}: narration anchors missing in capture: ${missing.join(", ")}`);
    }
    const bounds = anchored.map((l) => mk.get(l.anchor!)!);
    const end = mk.get("end")!;
    const segments: Segment[] = [];
    let cursor = 0;
    anchored.forEach((l, i) => {
      const start = i === 0 ? Math.max(0, bounds[0] - 0.3) : bounds[i];
      const stop = i + 1 < bounds.length ? bounds[i + 1] : end;
      const videoLen = Math.max(0.2, stop - start);
      const display = Math.max(videoLen, seconds.get(l.id)!.seconds + 0.5);
      lineOffsets.set(l.id, cursor + 0.15);
      const still = cap.stills.find((s) => s.name === l.anchor);
      const clicks = cap.markers.filter((m) => m.at && m.t >= start && m.t < stop)
        .map((m) => ({ frame: f(m.t - start), x: m.at!.x, y: m.at!.y }));
      segments.push({ video: `${assetBase}/${cap.video}`, startFrom: f(start), playFrames: f(videoLen),
        freezeFrames: f(display) - f(videoLen), from: f(cursor), label: l.anchor!, clicks,
        // The chip names what the sentence describes; it leaves when the sentence ends (plus a short tail).
        callout: l.callout ? { ...l.callout, frames: Math.min(f(display), Math.ceil(seconds.get(l.id)!.seconds * fps) + f(0.8)) }
                           : undefined,
        inset: still ? { src: `${assetBase}/${still.file}`, width: still.width, height: still.height, delay: f(1.0) }
                     : undefined });
      cursor += f(display) / fps;
    });
    sceneSegments.set(id, segments);
    specs.push({ id, videoSeconds: cursor, narrationSeconds: 0, padSeconds: 0 });
  }

  const timeline = buildTimeline(specs, fps);
  const audio: AudioClip[] = [];
  const captions: Cue[] = [];
  for (const scene of timeline.scenes) {
    for (const l of lines.filter((x) => x.scene === scene.id)) {
      const v = seconds.get(l.id)!;
      const startSec = scene.from / fps + lineOffsets.get(l.id)!;
      if (v.file) audio.push({ src: `${assetBase}/${l.id}.wav`, from: f(startSec), durationInFrames: Math.ceil(v.seconds * fps) });
      captions.push(...splitIntoCues({ text: l.text, start: startSec, end: startSec + v.seconds }, CAPTION_CHARS));
    }
  }
  // The intro shows a real phone capture of Scenario A's result while it says what CEKBAO does (product on screen early).
  const teaserStill = captures.conflict?.stills.find((s) => s.name === "mobile");
  const scenes: PlannedScene[] = timeline.scenes.map((s) => {
    const narrated = !CAPTURE_SCENES.includes(s.id) && !TITLE_CARDS[s.id];
    return {
      ...s, segments: sceneSegments.get(s.id) ?? [], title: captures[s.id]?.title, code: captures[s.id]?.code,
      card: TITLE_CARDS[s.id] ? { title: TITLE_CARDS[s.id].title, subtitle: TITLE_CARDS[s.id].subtitle } : undefined,
      beats: narrated ? lines.filter((l) => l.scene === s.id).map((l) => f(lineOffsets.get(l.id)!)) : undefined,
      teaser: s.id === "intro" && teaserStill
        ? { src: `${assetBase}/${teaserStill.file}`, width: teaserStill.width, height: teaserStill.height } : undefined,
      // The timeline restates Scenario B's two results exactly as the app showed them (next payment, earlier payment).
      verdicts: s.id === "policy_timeline" ? captures.policy_change?.headlines : undefined };
  });
  const footageFrames = scenes.filter((s) => s.segments.length).reduce((n, s) => n + s.durationInFrames, 0);
  const intro = scenes.find((s) => s.id === "intro");
  const firstFootage = scenes.find((s) => s.segments.length);
  const productFrame = intro?.teaser && intro.beats && intro.beats.length > 1 ? intro.from + intro.beats[1]
                                                                             : firstFootage?.from ?? 0;
  const viewport = Object.values(captures)[0]?.viewport ?? { width: 1440, height: 810 };
  return { fps, width: 1920, height: 1080, viewport, totalFrames: timeline.totalFrames, footageFrames, productFrame,
           scenes, audio, sfx: soundEffects(scenes, fps, timeline.totalFrames), captions, facts };
}

/** Whoosh on every scene change, a pop when a zoom or an animation beat appears, a click on every recorded click. */
export function soundEffects(scenes: PlannedScene[], fps: number, totalFrames: number): SfxClip[] {
  const out: SfxClip[] = [];
  const add = (kind: keyof typeof SFX, at: number) => {
    const fx = SFX[kind];
    const length = Math.min(Math.ceil(fx.seconds * fps), totalFrames - at);
    if (at >= 0 && length > 0) out.push({ src: fx.src, from: at, durationInFrames: length, volume: fx.volume });
  };
  for (const s of scenes) {
    add("whoosh", s.from);
    for (const b of (s.beats ?? []).slice(1)) add("pop", s.from + b);
    for (const g of s.segments) {
      if (g.inset) add("pop", s.from + g.from + g.inset.delay);
      for (const c of g.clicks) add("click", s.from + g.from + c.frame);
    }
  }
  return out.sort((a, b) => a.from - b.from);
}
