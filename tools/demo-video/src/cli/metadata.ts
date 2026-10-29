// demo:metadata: timeline.json (shared source of truth), title options, description, chapters and the final
// production rundown, all derived from the rendered edit. Duration comes from ffprobe of the rendered MP4.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { VERIFIED_SOURCES, buildChapters, chapterText, validateChapters } from "../pipeline/youtube.ts";
import { ARTIFACTS, REPO, ffprobe, latestBuild, readJson, writeJson } from "../pipeline/util.ts";

const build = latestBuild();
const manifest = readJson(path.join(build.dir, "evidence-manifest.json"));
if (!manifest.render) throw new Error("Render the video first (npm run demo:render).");
const plan = readJson(path.join(build.dir, "plan.json")).plan;
const narration = fs.readFileSync(path.join(ARTIFACTS, "narration.md"), "utf8");
const mp4 = path.join(REPO, manifest.render.output);
const duration = Number(ffprobe(mp4).format.duration);
const planned = plan.totalFrames / plan.fps;
if (Math.abs(duration - planned) > 0.1) throw new Error(`rendered duration ${duration} s differs from the plan (${planned} s)`);
const mode: string = manifest.inference_summary.mode;
const live = mode === "live" || mode === "replay";
const repo = manifest.project.repository.replace(/\.git$/, "");
const linesFor = (scene: string) => [...narration.matchAll(new RegExp(`## ${scene}\\n\\n([\\s\\S]*?)(?:\\n## |$)`, "g"))]
  .flatMap((m) => m[1].split("\n").filter((l) => l.startsWith("- ")).map((l) => l.slice(2).replace(/\s+_\(on screen.*$/, "")));

const PURPOSE: Record<string, string> = {
  intro: "Animate the problem: a tuition email with a new account, the reported scam pattern, and what CEKBAO checks",
  policy_timeline: "Animate how the payment date selects the policy version (the distinctive moment)",
  title_conflict: "State the verification question", conflict: "Check a suspicious instruction end to end in the real app",
  title_policy_change: "Introduce the date scenario", policy_change: "Show that the payment date selects the policy version",
  title_insufficient: "Introduce the authority scenario", insufficient: "Show insufficient evidence from a publisher without authority",
  escalation: "Show escalation to an institution reviewer", nvidia: "State the NVIDIA and Nebius integration status with evidence",
  results: "Report measured results, limits and the code link",
};
const POLICE_ADVISORY = VERIFIED_SOURCES.policeAdvisory.url;
const chapters = buildChapters(plan.scenes, plan.fps, duration, mode);
const chapterErrors = validateChapters(chapters, duration);
if (chapterErrors.length) throw new Error(`chapters invalid: ${chapterErrors.join("; ")}`);
const chapterOf = (frame: number) => [...chapters].reverse().find((c) => c.start <= frame / plan.fps)!.title;
const sha256 = crypto.createHash("sha256").update(fs.readFileSync(mp4)).digest("hex");

const timeline = {
  status: "final", generated_at: new Date().toISOString(), build_id: build.id, video: manifest.render.output, sha256,
  fps: plan.fps, total_frames: plan.totalFrames, duration_seconds: Number(duration.toFixed(3)), inference_mode: mode,
  scenes: plan.scenes.map((s: any) => ({
    id: s.id, start_frame: s.from, end_frame: s.from + s.durationInFrames, start: +(s.from / plan.fps).toFixed(3),
    end: +((s.from + s.durationInFrames) / plan.fps).toFixed(3), purpose: PURPOSE[s.id], chapter: chapterOf(s.from),
    narration: linesFor(s.id),
    on_screen_text: s.card ? [s.card.subtitle, s.card.title] : s.segments.length ? [`Scenario ${s.code}: ${s.title}`] : [s.id],
    source_footage: s.segments.map((g: any) => ({ clip: path.basename(g.video), from_seconds: +(g.startFrom / plan.fps).toFixed(2),
      to_seconds: +((g.startFrom + g.playFrames) / plan.fps).toFixed(2), hold_seconds: +(g.freezeFrames / plan.fps).toFixed(2),
      zoom: g.inset ? path.basename(g.inset.src) : null, marker: g.label })),
    evidence_refs: s.segments.length
      ? [`case ${manifest.scenarios.find((x: any) => x.key === s.id)?.case_ref ?? "(reviewer view of scenario C)"}`, "evidence-manifest.json"]
      : s.id === "nvidia" ? ["docs/policyguard/NVIDIA_NEBIUS.md", "evidence-manifest.json#inference_summary"]
      : s.id === "results" ? ["evidence-manifest.json#measurements"]
      : s.id === "intro" ? [POLICE_ADVISORY, "Scenario A result capture (teaser)"]
      : s.id === "policy_timeline" ? ["policyguard/seed.py (synthetic policy versions 2025.1 and 2026.1)"] : [],
  })),
  chapters,
};
writeJson(path.join(ARTIFACTS, "timeline.json"), timeline);

const titles = live ? [
  "CEKBAO: Checking Payment Instructions Against Policy | NVIDIA Nemotron on Nebius",
  "CEKBAO Demo: Payee Changes, Policy Dates and Evidence with NVIDIA on Nebius",
  "CEKBAO: Does This Payment Instruction Match the Policy on Its Date?",
] : [
  "CEKBAO: Checking Payment Instructions Against Institution Policy",
  "CEKBAO Demo: Payee Changes, Policy Versions and Payment Dates",
  "CEKBAO: Does This Payment Instruction Match the Policy on Its Date?",
];
fs.writeFileSync(path.join(ARTIFACTS, "youtube-title-options.md"), [
  "# YouTube title options", "", `Video build \`${build.id}\`; inference in this recording: **${mode}**.`, "",
  ...titles.map((t, i) => `${i + 1}. ${t} (${t.length} characters)${i === 0 ? " (recommended)" : ""}`), "",
  "Recommendation: option 1 leads with CEKBAO and the demonstrated purpose and stays within the 100-character limit.",
  live ? "NVIDIA and Nebius appear because the recording contains a live or recorded model call."
       : "NVIDIA and Nebius are not in the title because the model was not called in this recording.", ""].join("\n"));
fs.writeFileSync(path.join(ARTIFACTS, "youtube-title.txt"), titles[0] + "\n");

const m = manifest.measurements;
const description = [
  "CEKBAO checks whether a payment instruction matches the payment policy an institution has published for the payment date. " +
  "It shows the policy evidence and the next step, and it never moves money or confirms that a payment arrived.",
  "",
  "In this demo the running app checks three synthetic cases: an email that names a new payee, an old invoice whose account " +
  "changed when a new policy version took effect, and a deposit request backed only by a page from a publisher without " +
  "authority.",
  "",
  "Links",
  `Code: ${repo}`,
  `Reported scam pattern (Singapore Police Force advisory, 19 March 2026): ${POLICE_ADVISORY}`,
  "",
  "Chapters",
  chapterText(chapters),
  "",
  "How it works",
  "- A check is saved first (HTTP 202 after a database commit); a separate worker processes it.",
  "- Policy versions have validity periods. The check uses the version valid on the payment date, and an earlier payment is assessed separately from a new one.",
  "- Each result compares the instruction with the policy detail by detail and shows the policy quote, its version, its effective period and the publisher's authority.",
  live
    ? `- Model: ${manifest.inference_summary.model_id} on Nebius Token Factory reads the instruction and proposes fields with exact quotes; code checks every quote and fixed rules decide. Measured latency in this recording: ${(manifest.inference_summary.latency_ms / 1000).toFixed(1)} s.`
    : "- Model: the app is built to read instructions with NVIDIA Nemotron 3 Nano (nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B) on Nebius Token Factory, with quote checks and fixed rules deciding. In this recording the model was not called because no API key or budget was configured; fixed rules read every instruction.",
  `- Measured on this build: ${m.tests_passed} automated tests passed; axe-core found ${m.axe_violations} WCAG violations on the audited pages.`,
  "",
  "Limits and disclosure",
  "- All institutions, people, accounts and sources are synthetic. They are not customers or partners.",
  "- A policy match is not a payment confirmation; payment status is always shown as unknown.",
  "- No user testing has been done yet.",
  "- The narration uses a synthetic voice.",
  "",
  "Credits",
  "Font: Inter (SIL Open Font License 1.1). Voice: Kokoro-82M via kokoro-onnx (Apache-2.0). Sound effects: original, synthesized. App recorded with Playwright; video composed with Remotion.",
  "",
  "#FinTech #Hackathon",
].join("\n");
fs.writeFileSync(path.join(ARTIFACTS, "youtube-description.txt"), description + "\n");
fs.writeFileSync(path.join(ARTIFACTS, "youtube-chapters.txt"), chapterText(chapters) + "\n");

const fmt = (f: number) => `${Math.floor(f / plan.fps / 60)}:${(f / plan.fps % 60).toFixed(1).padStart(4, "0")}`;
const rundown = ["# Production rundown (final timing)", "",
  `Timing source: rendered file \`${manifest.render.output}\` (${duration.toFixed(2)} s, ${plan.totalFrames} frames at ${plan.fps} fps), build \`${build.id}\`. ` +
  "The planned storyboard is `storyboard.md`; only this final rundown belongs with the upload package.", "",
  "| Start | End | Duration | Scene purpose | Visible action | Narration | Annotation | Source clip | Evidence |",
  "|---|---|---|---|---|---|---|---|---|"];
for (const s of timeline.scenes) {
  const planned_ = plan.scenes.find((x: any) => x.id === s.id);
  if (!planned_.segments.length) {
    const kind = s.id.startsWith("title") ? "animated title card" : s.id === "intro" || s.id === "policy_timeline"
      ? "animated explainer (synthetic example)" : "animated evidence card";
    rundown.push(`| ${fmt(s.start_frame)} | ${fmt(s.end_frame)} | ${((s.end_frame - s.start_frame) / plan.fps).toFixed(1)} s | ${s.purpose} | ${s.on_screen_text.join(": ")} | ${s.narration.join(" ")} | ${kind} | composition | ${s.evidence_refs.join(", ")} |`);
    continue;
  }
  for (const g of planned_.segments) {
    const start = s.start_frame + g.from, end = start + g.playFrames + g.freezeFrames;
    const said = s.narration.find((n: string, i: number) => i === planned_.segments.indexOf(g)) ?? "";
    rundown.push(`| ${fmt(start)} | ${fmt(end)} | ${((end - start) / plan.fps).toFixed(1)} s | ${s.purpose} | ${g.label.replace(/_/g, " ")} | ${said} | ${g.inset ? "zoom on the element under discussion" : ""}${g.clicks.length ? `${g.inset ? "; " : ""}click indicator` : ""} | ${path.basename(g.video)} ${(g.startFrom / plan.fps).toFixed(1)}–${((g.startFrom + g.playFrames) / plan.fps).toFixed(1)} s | ${s.evidence_refs[0]} |`);
  }
}
fs.writeFileSync(path.join(ARTIFACTS, "production-rundown.md"), rundown.join("\n") + "\n");
console.log(`timeline, titles, description (${description.length} chars), ${chapters.length} chapters, rundown written`);
console.log(chapterText(chapters));
