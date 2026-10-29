// rendering: narration audio, plan, captions and the Remotion render. Uses the stored capture only;
// it never starts the app or calls a model.
import fs from "node:fs";
import path from "node:path";
import type { DemoConfig } from "./config.ts";
import type { ScenarioCapture } from "./capture.ts";
import type { Caption } from "@remotion/captions";
import { toSrt, validateCues, type Cue } from "./captions.ts";
import { narrationMarkdown, buildScript, type Facts, type NarrationLine } from "./narration.ts";
import { makePlan, CAPTION_CHARS, type Plan } from "./plan.ts";
import { chooseTts } from "./tts.ts";
import { ARTIFACTS, NPX_REMOTION, PUBLIC_BUILD, REPO, TOOL_DIR, readJson, run, writeJson } from "./util.ts";

// YouTube recommended upload settings for 1080p30 SDR (YouTube Help 1722171): H.264 High, 4:2:0, at least 8 Mbps,
// BT.709 tags, AAC-LC 48 kHz at 384 kbps. GOP and B-frames are set in remotion.config.ts.
export const YOUTUBE_ENCODING = ["--codec=h264", "--pixel-format=yuv420p", "--video-bitrate=10M", "--color-space=bt709",
                                 "--audio-codec=aac", "--audio-bitrate=384k"];

export type RenderResult = { output: string; srt: string; plan: Plan; kind: string; tts: string; audio: boolean;
                             renderSeconds: number; smoke: string };

export function outputNames(cfg: DemoConfig, kind: string) {
  const base = kind === "final" ? cfg.video.output : cfg.video.output.replace(/\.mp4$/, "-preview-MOCK.mp4");
  return { mp4: path.join(REPO, base), srt: path.join(REPO, base.replace(/\.mp4$/, ".srt")) };
}

export function render(cfg: DemoConfig, build: { id: string; dir: string },
                       opts: { concurrency: number; planOnly?: boolean }): RenderResult {
  const capture = readJson(path.join(build.dir, "capture.json"));
  const manifest = readJson(path.join(build.dir, "evidence-manifest.json"));
  const captures: Record<string, ScenarioCapture> = Object.fromEntries(capture.scenarios.map((s: ScenarioCapture) => [s.key, s]));
  const inf = manifest.inference_summary;
  const facts: Facts = { inferenceMode: inf.mode, modelId: inf.model_id, latencySeconds: inf.latency_ms ? inf.latency_ms / 1000 : null,
                         testsPassed: manifest.measurements.tests_passed, axeViolations: manifest.measurements.axe_violations,
                         repoUrl: manifest.project.repository };
  const lines = buildScript(captures, facts);
  const tts = chooseTts(cfg.tts);
  const audioDir = path.join(build.dir, "audio");
  const voiced = tts.synthesize(lines, audioDir);
  // Assets for Remotion live under public/build/<id>; the raw capture stays untouched.
  const assetDir = path.join(PUBLIC_BUILD, build.id);
  fs.mkdirSync(assetDir, { recursive: true });
  for (const f of fs.readdirSync(build.dir)) {
    if (/\.(webm|png)$/.test(f)) fs.copyFileSync(path.join(build.dir, f), path.join(assetDir, f));
  }
  for (const v of voiced) if (v.file) fs.copyFileSync(v.file, path.join(assetDir, path.basename(v.file)));
  // Original synthesized sound effects (deterministic), written next to the build assets.
  run(path.join(REPO, "video/.tts/venv/bin/python"), [path.join(TOOL_DIR, "sfx/make_sfx.py"), path.join(TOOL_DIR, "public/sfx")]);
  const kind = manifest.output_kind;
  const checks = capture.scenarios.filter((s: ScenarioCapture) => s.key !== "escalation");
  const plan = makePlan(lines, voiced, captures, `build/${build.id}`, cfg.video.fps, {
    preview: kind !== "final", mode: inf.mode, modelId: inf.model_id, latencyMs: inf.latency_ms,
    blocker: cfg.inference_blocker?.short ?? null,
    tokens: inf.tokens ?? null, checkedAt: inf.checked_at ?? null, blockedReason: inf.blocked_reason ?? null,
    license: "NVIDIA Nemotron Open Model License (open weights; not an OSI open-source licence)",
    testsPassed: manifest.measurements.tests_passed, axeViolations: manifest.measurements.axe_violations,
    lighthouseA11y: manifest.measurements.lighthouse_accessibility_min,
    decisions: checks.map((s: ScenarioCapture) => [s.code, s.headlines.length > 1
      ? `${s.headlines[0].replace(/\.$/, "")} for the next payment; ${s.headlines[1].charAt(0).toLowerCase()}${s.headlines[1].slice(1).replace(/\.$/, "")} for the earlier one`
      : s.headlines[0]]),
    repo: manifest.project.repository.replace(/^https?:\/\//, "").replace(/\.git$/, "") });
  const captionErrors = validateCues(plan.captions, CAPTION_CHARS);
  if (captionErrors.length) throw new Error(`caption errors: ${captionErrors.join("; ")}`);
  writeJson(path.join(PUBLIC_BUILD, "plan.json"), plan);
  const planFile = path.join(build.dir, "plan.json");
  writeJson(planFile, { plan });
  const names = outputNames(cfg, kind);
  fs.mkdirSync(ARTIFACTS, { recursive: true });
  fs.writeFileSync(names.srt, toSrt(plan.captions));
  writeJson(names.srt.replace(/\.srt$/, ".captions.json"), toCaptionJson(plan.captions));
  fs.writeFileSync(path.join(ARTIFACTS, "storyboard.md"), storyboard(plan, lines, captures, "planned"));
  fs.writeFileSync(path.join(ARTIFACTS, "narration.md"),
                   narrationMarkdown(lines, tts.hasAudio ? `synthetic voice, ${tts.name}` : "none (captions only)"));
  const entry = path.join(TOOL_DIR, "src/remotion/index.ts");
  if (opts.planOnly) {        // narration, captions and plan only: for checking single frames with `remotion still`
    return { output: "", srt: names.srt, plan, kind, tts: tts.name, audio: tts.hasAudio, renderSeconds: 0, smoke: "" };
  }
  // Representative segment first: Scenario A from its result, 10 s at full resolution with audio, plus a still.
  const conflict = plan.scenes.find((s) => s.id === "conflict")!;
  const resultSeg = conflict.segments.find((s) => s.label === "result_shown")!;
  const s0 = conflict.from + resultSeg.from;
  const smoke = path.join(ARTIFACTS, "smoke", `${build.id}-segment.mp4`);
  fs.mkdirSync(path.dirname(smoke), { recursive: true });
  run(NPX_REMOTION, ["render", entry, "CekbaoDemo", smoke, `--props=${planFile}`, `--frames=${s0}-${s0 + 299}`,
                     ...YOUTUBE_ENCODING, `--concurrency=${opts.concurrency}`,
                     "--log=error"], { cwd: TOOL_DIR });
  run(NPX_REMOTION, ["still", entry, "CekbaoDemo", smoke.replace(/\.mp4$/, ".png"), `--props=${planFile}`,
                     `--frame=${s0 + resultSeg.inset!.delay + 30}`, "--log=error"], { cwd: TOOL_DIR });
  const started = Date.now();
  const tmp = names.mp4.replace(/\.mp4$/, ".tmp.mp4");
  run(NPX_REMOTION, ["render", entry, "CekbaoDemo", tmp, `--props=${planFile}`, ...YOUTUBE_ENCODING,
                     `--concurrency=${opts.concurrency}`, "--timeout=120000", "--log=error"], { cwd: TOOL_DIR });
  const renderSeconds = (Date.now() - started) / 1000;
  // Remux without re-encoding: moov first (fast start) and no edit lists, as YouTube recommends.
  run(NPX_REMOTION, ["ffmpeg", "-y", "-v", "error", "-i", tmp, "-c", "copy", "-movflags", "+faststart+negative_cts_offsets",
                     "-use_editlist", "0", names.mp4], { cwd: TOOL_DIR });
  fs.rmSync(tmp);
  return { output: names.mp4, srt: names.srt, plan, kind, tts: tts.name, audio: tts.hasAudio, renderSeconds,
           smoke };
}

/** Captions in Remotion's Caption JSON format (one entry per on-screen cue). */
export function toCaptionJson(cues: Cue[]): Caption[] {
  return cues.map((c) => ({ text: c.lines.join(" "), startMs: Math.round(c.start * 1000), endMs: Math.round(c.end * 1000),
                            timestampMs: Math.round(c.start * 1000), confidence: null }));
}

const mmss = (frames: number, fps: number) => {
  const s = frames / fps;
  return `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, "0")}`;
};

export function storyboard(plan: Plan, lines: NarrationLine[], captures: Record<string, ScenarioCapture>, label: string): string {
  const out = [`# Storyboard and timeline (${label})`, "",
    `${plan.totalFrames} frames at ${plan.fps} fps = ${(plan.totalFrames / plan.fps).toFixed(1)} s. ` +
    `Application footage: ${Math.round((plan.footageFrames / plan.totalFrames) * 100)} % of the edit.`, "",
    "| Start | End | Scene | Segment | Source | Zoom | Narration |", "|---|---|---|---|---|---|---|"];
  for (const s of plan.scenes) {
    if (!s.segments.length) {
      const said = lines.filter((l) => l.scene === s.id).map((l) => l.text).join(" ");
      out.push(`| ${mmss(s.from, plan.fps)} | ${mmss(s.from + s.durationInFrames, plan.fps)} | ${s.id} | ${s.card ? "title card" : "explanation"} | composition | | ${said} |`);
      continue;
    }
    for (const seg of s.segments) {
      const said = lines.find((l) => l.scene === s.id && l.anchor === seg.label)?.text ?? "";
      const start = s.from + seg.from, end = start + seg.playFrames + seg.freezeFrames;
      out.push(`| ${mmss(start, plan.fps)} | ${mmss(end, plan.fps)} | ${s.id} | ${seg.label} | ${captures[s.id].video} @ ${(seg.startFrom / plan.fps).toFixed(1)} s` +
               `${seg.freezeFrames ? ` (+${(seg.freezeFrames / plan.fps).toFixed(1)} s hold)` : ""} | ${seg.inset ? "yes" : ""} | ${said} |`);
    }
  }
  return out.join("\n") + "\n";
}
