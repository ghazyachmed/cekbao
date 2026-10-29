// demo:render: narration, captions and MP4 from the latest stored capture. No model calls, no app access.
import fs from "node:fs";
import path from "node:path";
import { loadConfig } from "../pipeline/config.ts";
import { render } from "../pipeline/render.ts";
import { ARTIFACTS, REPO, TOOL_DIR, latestBuild, readJson, writeJson } from "../pipeline/util.ts";

const cfg = loadConfig(path.join(TOOL_DIR, "demo.config.json"));
const build = latestBuild();
const concurrency = Number(process.env.DEMO_RENDER_CONCURRENCY ?? 4);
console.log(`render ${build.id} (concurrency ${concurrency})`);
const planOnly = process.env.DEMO_PLAN_ONLY === "1";
const r = render(cfg, build, { concurrency, planOnly });
if (planOnly) {
  console.log(`plan written: public/build/plan.json (${(r.plan.totalFrames / r.plan.fps).toFixed(1)} s, ` +
              `footage ${Math.round((r.plan.footageFrames / r.plan.totalFrames) * 100)} %, product at ${(r.plan.productFrame / r.plan.fps).toFixed(1)} s)`);
  process.exit(0);
}
const manifest = readJson(path.join(build.dir, "evidence-manifest.json"));
manifest.render = { output: path.relative(REPO, r.output), srt: path.relative(REPO, r.srt), kind: r.kind,
                    narration_audio: r.audio ? r.tts : "none", music: "none", render_seconds: r.renderSeconds,
                    total_frames: r.plan.totalFrames, fps: r.plan.fps, smoke_render: path.relative(REPO, r.smoke),
                    scenes: r.plan.scenes.map((s) => ({ id: s.id, from: s.from, frames: s.durationInFrames })) };
writeJson(path.join(build.dir, "evidence-manifest.json"), manifest);
fs.copyFileSync(path.join(build.dir, "evidence-manifest.json"), path.join(ARTIFACTS, "evidence-manifest.json"));
console.log(`rendered ${path.relative(REPO, r.output)} (${(r.plan.totalFrames / r.plan.fps).toFixed(1)} s) in ${r.renderSeconds.toFixed(0)} s`);
