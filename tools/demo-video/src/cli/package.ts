// demo:package: thumbnails + metadata + publishing checklist, next to the final video and subtitles.
// Prepares files only; nothing is uploaded or published.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { ARTIFACTS, REPO, TOOL_DIR, latestBuild, readJson } from "../pipeline/util.ts";

for (const step of ["thumbnail", "metadata"]) {
  execFileSync(process.execPath, [path.join(TOOL_DIR, "src/cli", `${step}.ts`)], { stdio: "inherit", cwd: TOOL_DIR });
}
const choice = (process.env.DEMO_THUMBNAIL ?? "A").toUpperCase();
fs.copyFileSync(path.join(ARTIFACTS, `thumbnail-${choice.toLowerCase()}.jpg`), path.join(ARTIFACTS, "thumbnail-final.jpg"));
const build = latestBuild();
const manifest = readJson(path.join(build.dir, "evidence-manifest.json"));
const final = manifest.output_kind === "final";
const git = manifest.git;
const lines = [
  "# Publishing checklist", "", `Build \`${build.id}\`. Prepared ${new Date().toISOString()}. Nothing has been uploaded or published.`, "",
  "| Item | Status |", "|---|---|",
  `| Video | ${path.basename(manifest.render.output)}: ${final ? "final (live or recorded NVIDIA inference)" : "**preview (MOCK)**: the NVIDIA model was not called; not a final submission video"} |`,
  `| Thumbnail | thumbnail-final.jpg = variant ${choice} (see thumbnails/ and youtube-package-validation.md) |`,
  "| Title, description, chapters | youtube-title.txt, youtube-description.txt, youtube-chapters.txt |",
  `| Code link | ${manifest.project.repository} is public (checked HTTP 200 on 2026-10-28), but the PolicyGuard work in this video is ${git.dirty ? "**not yet committed or pushed**" : "committed"}: push before publishing |`,
  "| Demo or Devpost link | not provided; omitted from the description |",
  "| YouTube URL | not created (no upload performed) |",
  `| Live NVIDIA evidence | ${final ? "present" : "missing: set NEBIUS_API_KEY, NEBIUS_MODEL_ID, PG_INFERENCE_BUDGET_USD and PG_MAX_PAID_CALLS in .env.local, run scripts/nebius_live_check.py, then npm run demo:build and npm run demo:package"} |`,
  "| Human review | watch the full video and listen to the narration before upload |", "",
];
fs.writeFileSync(path.join(ARTIFACTS, "publishing-checklist.md"), lines.join("\n"));
console.log(`package prepared in ${path.relative(REPO, ARTIFACTS)} (thumbnail ${choice}; ${final ? "final" : "preview"})`);
