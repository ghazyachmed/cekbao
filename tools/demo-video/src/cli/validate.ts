// demo:validate: probe the MP4, check captions, decode frames for every scene and transition, write the report.
import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../pipeline/config.ts";
import { validateCues, type Cue } from "../pipeline/captions.ts";
import { CAPTION_CHARS } from "../pipeline/plan.ts";
import { SCENARIOS } from "../pipeline/scenarios.ts";
import { checkDuration } from "../pipeline/timeline.ts";
import { checkProbe, checkYoutubeRecommended, hasEditList, maxKeyframeGap, moovBeforeMdat, type Check } from "../pipeline/validate.ts";
import { ARTIFACTS, NPX_REMOTION, REPO, TOOL_DIR, ffprobe, latestBuild, readJson, run, writeJson } from "../pipeline/util.ts";

const cfg = loadConfig(path.join(TOOL_DIR, "demo.config.json"));
const build = latestBuild();
const manifest = readJson(path.join(build.dir, "evidence-manifest.json"));
if (!manifest.render) throw new Error("No render recorded for the latest capture. Run npm run demo:render first.");
const mp4 = path.join(REPO, manifest.render.output);
const plan = readJson(path.join(build.dir, "plan.json")).plan;
const probe = ffprobe(mp4);
const audioExpected = manifest.render.narration_audio !== "none";
const checks: Check[] = checkProbe(probe, { width: cfg.video.width, height: cfg.video.height, fps: cfg.video.fps,
                                            limit: cfg.video.duration_limit_seconds, expectAudio: audioExpected });
const head = Buffer.alloc(Math.min(fs.statSync(mp4).size, 32 * 1024 * 1024));   // moov sits at the front (fast start)
const fd = fs.openSync(mp4, "r"); fs.readSync(fd, head, 0, head.length, 0); fs.closeSync(fd);
checks.push({ name: "faststart", ok: moovBeforeMdat(head), detail: "moov atom before mdat" });
// Keyframe flags of the first 20 seconds, for the GOP recommendation.
const keyFlags = run(NPX_REMOTION, ["ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals", "%+20",
                                    "-show_entries", "frame=key_frame", "-of", "csv=p=0", mp4], { cwd: TOOL_DIR })
  .split(/\s+/).filter(Boolean).map(Number);
checks.push(...checkYoutubeRecommended(probe, { height: cfg.video.height, fps: cfg.video.fps,
                                                keyframeGap: maxKeyframeGap(keyFlags), editList: hasEditList(head) }));
const cues: Cue[] = plan.captions;
const captionErrors = validateCues(cues, CAPTION_CHARS);
checks.push({ name: "captions", ok: captionErrors.length === 0,
              detail: captionErrors.length ? captionErrors.join("; ") : `${cues.length} cues, max 2 lines, no overlap` });
const duration = Number(probe.format.duration);
// Full decode: every video frame and audio sample through AVFoundation.
const decode = JSON.parse(run("swift", [path.join(TOOL_DIR, "qa/decode_all.swift"), mp4]));
const expectedFrames = Math.round(duration * cfg.video.fps);
checks.push({ name: "full_decode", ok: decode.status === "completed" && Math.abs(decode.video_frames_decoded - expectedFrames) <= 2,
              detail: `${decode.status}; ${decode.video_frames_decoded} video frames decoded (expected about ${expectedFrames}); ${decode.audio_samples ?? 0} audio samples` });
if (audioExpected) {
  // Loudness per narration line: mean of the 0.5 s RMS windows inside each clip (pauses below -45 dBFS excluded).
  const win: number[] = decode.audio_rms_windows_dbfs;
  const perLine = plan.audio.map((a: any) => {
    const from = Math.ceil((a.from / plan.fps) * 2), to = Math.floor(((a.from + a.durationInFrames) / plan.fps) * 2);
    const w = win.slice(from, to).filter((x) => x > -45);
    return w.length ? 10 * Math.log10(w.reduce((n, x) => n + 10 ** (x / 10), 0) / w.length) : -120;
  }).filter((x: number) => x > -100);
  const spread = Math.max(...perLine) - Math.min(...perLine);
  checks.push({ name: "audio_levels", ok: decode.audio_peak_dbfs <= -1 && decode.audio_clipped_samples === 0 && spread <= 6,
                detail: `peak ${decode.audio_peak_dbfs.toFixed(1)} dBFS, clipped samples ${decode.audio_clipped_samples}, ` +
                        `${perLine.length} narration lines between ${Math.min(...perLine).toFixed(1)} and ${Math.max(...perLine).toFixed(1)} dBFS RMS ` +
                        `(spread ${spread.toFixed(1)} dB, limit 6 dB)` });
}
const footageShare = plan.footageFrames / plan.totalFrames;
const dur = checkDuration(duration, cfg.video.duration_target_seconds, cfg.video.duration_limit_seconds);

// Frames: the middle of every segment plus both sides of every scene boundary.
const fps = plan.fps;
const points: { t: number; label: string }[] = [];
for (const s of plan.scenes) {
  points.push({ t: (s.from + 3) / fps, label: `${s.id} start` });
  for (const seg of s.segments) points.push({ t: (s.from + seg.from + (seg.playFrames + seg.freezeFrames) / 2) / fps,
                                              label: `${s.id}: ${seg.label}` });
  if (!s.segments.length) points.push({ t: (s.from + s.durationInFrames / 2) / fps, label: `${s.id} middle` });
  points.push({ t: (s.from + s.durationInFrames - 3) / fps, label: `${s.id} end` });
}
for (let t = 2; t < duration - 0.5; t += 2) points.push({ t, label: "every 2 s" });
points.sort((a, b) => a.t - b.t);
for (const p of points) p.t = Number(p.t.toFixed(3));   // the same value goes to the decoder and the analyser
const qa = path.join(ARTIFACTS, "qa", build.id);
const framesDir = path.join(qa, "frames");
fs.mkdirSync(framesDir, { recursive: true });
run("swift", [path.join(TOOL_DIR, "qa/extract_frames.swift"), mp4, framesDir, ...points.map((p) => String(p.t))]);
writeJson(path.join(qa, "points.json"), points);
const frameReport = JSON.parse(run(path.join(REPO, "video/.tts/venv/bin/python"),
  [path.join(TOOL_DIR, "qa/frames.py"), framesDir, path.join(qa, "points.json"), qa]));
const bad = frameReport.filter((f: any) => !f.ok);
checks.push({ name: "frames", ok: bad.length === 0, detail: `${frameReport.length} decoded frames; ` +
              (bad.length ? `${bad.length} problems: ${bad.map((b: any) => `${b.t.toFixed(1)}s ${b.issue}`).join(", ")}` : "no blank frames") });
writeJson(path.join(qa, "frames.json"), frameReport);

const technicalOk = checks.every((c) => c.ok);
const final = manifest.output_kind === "final";
const status = {
  CODE_IMPLEMENTED: true,
  CAPTURED: manifest.scenarios.length === SCENARIOS.length,
  RENDERED: fs.existsSync(mp4),
  VALIDATED: technicalOk && dur.withinLimit,
  SUBMISSION_READY: technicalOk && dur.withinLimit && final,
};
const lines = [
  "# Demo video validation report", "",
  `Build: \`${build.id}\`. Commit: \`${manifest.git.commit.slice(0, 12)}\`${manifest.git.dirty ? ` with ${manifest.git.changed_files} uncommitted changes` : ""}. Generated ${new Date().toISOString()}.`, "",
  "## Status", "", "| Stage | Status |", "|---|---|",
  ...Object.entries(status).map(([k, v]) => `| ${k} | ${v ? "yes" : "NO"} |`), "",
  final ? "Output kind: **final** (every scenario used live or recorded NVIDIA inference)."
        : `Output kind: **preview (MOCK)**. ${manifest.inference_summary.blocked_reason}. The file is named as a preview and is not a submission video.`, "",
  "## Official duration rule", "",
  `${cfg.rules_source?.video_rule} Source: ${cfg.rules_source?.url} (checked ${cfg.rules_source?.checked_on}).`,
  `Measured duration ${duration.toFixed(2)} s; editorial target ${dur.target} s (deviation ${dur.deviationFromTargetSeconds} s); limit ${dur.limit} s: ${dur.withinLimit ? "within limit" : "OVER LIMIT"}.`, "",
  "## Technical checks (ffprobe and file inspection)", "", "| Check | Result | Detail |", "|---|---|---|",
  ...checks.map((c) => `| ${c.name} | ${c.ok ? "pass" : "FAIL"} | ${c.detail} |`), "",
  `Application footage share: ${Math.round(footageShare * 100)} % of the edit (editorial target 60 %, not a competition rule). ` +
  `Product first visible at ${((plan.productFrame ?? plan.scenes.find((x: any) => x.segments.length).from) / plan.fps).toFixed(1)} s ` +
  `(real app capture). Sound effects: ${plan.sfx?.length ?? 0} original synthesized cues under the narration.`, "",
  "## Scenarios captured from the running app", "", "| Scenario | Headlines shown by the app | Read by |", "|---|---|---|",
  ...manifest.scenarios.map((s: any) => `| ${s.code} ${s.key} | ${s.headlines.join(" / ")} | ${s.inference ? `${s.inference.mode}${s.inference.model_id ? ` (${s.inference.model_id})` : ""}` : "reviewer step (no reading)"} |`), "",
  "## Frame review", "",
  `Frames decoded from the final MP4 with AVFoundation: ${frameReport.length} (scene starts, ends, every segment, every 2 s). ` +
  `Contact sheet: \`${path.relative(REPO, path.join(qa, "contact_sheet.jpg"))}\`. 720p copies for legibility: \`${path.relative(REPO, path.join(qa, "720p"))}\`.`, "",
  "## Not done by this script", "",
  "- Continuous real-time playback by a person (this script decodes every frame and samples images every 2 s).",
  "- Listening test by ear (pronunciation of CEKBAO, NVIDIA, Nebius); levels are measured numerically above.",
  "- Review by the hackathon organisers' player or upload target.", "",
];
fs.writeFileSync(path.join(ARTIFACTS, "validation-report.md"), lines.join("\n"));
writeJson(path.join(qa, "probe.json"), probe);
console.log(lines.slice(4, 11).join("\n"));
for (const c of checks) console.log(`${c.ok ? "pass" : "FAIL"}  ${c.name}: ${c.detail}`);
process.exitCode = status.VALIDATED ? 0 : 1;
