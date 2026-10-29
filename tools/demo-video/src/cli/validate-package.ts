// demo:validate-package: files, thumbnail sizes, links, chapters vs the rendered video, lengths and claims.
import fs from "node:fs";
import path from "node:path";
import { VERIFIED_SOURCES, checkClaims, checkLengths, validateChapters, type Chapter } from "../pipeline/youtube.ts";
import { ARTIFACTS, REPO, ffprobe, latestBuild, readJson, run } from "../pipeline/util.ts";

type Row = { name: string; ok: boolean; detail: string };
const rows: Row[] = [];
const add = (name: string, ok: boolean, detail: string) => rows.push({ name, ok, detail });
const build = latestBuild();
const manifest = readJson(path.join(build.dir, "evidence-manifest.json"));
const mode: string = manifest.inference_summary.mode;
const A = (f: string) => path.join(ARTIFACTS, f);
const video = path.join(REPO, manifest.render.output);
const required = [path.basename(video), path.basename(video).replace(/\.mp4$/, ".srt"), path.basename(video).replace(/\.mp4$/, ".captions.json"),
  "youtube-title-options.md", "youtube-title.txt", "youtube-description.txt", "youtube-chapters.txt", "production-rundown.md",
  "timeline.json", "thumbnail-a.jpg", "thumbnail-b.jpg", "thumbnail-c.jpg", "thumbnail-final.jpg", "narration.md",
  "evidence-manifest.json", "validation-report.md", "storyboard.md", "publishing-checklist.md"];
const missing = required.filter((f) => !fs.existsSync(A(f)));
add("required files", missing.length === 0, missing.length ? `missing: ${missing.join(", ")}` : `${required.length} files present`);

const sizes = readJson(A("thumbnails/thumbnails.json")).sizes;
for (const v of ["A", "B", "C"]) {
  const s = sizes[v];
  add(`thumbnail ${v}`, s.master[0] === 3840 && s.master[1] === 2160 && s.jpg_bytes < 2_000_000,
      `master ${s.master.join("x")}, JPG ${(s.jpg_bytes / 1e6).toFixed(2)} MB at quality ${s.jpg_quality}`);
}
const finalJpg = run("sips", ["-g", "pixelWidth", "-g", "pixelHeight", A("thumbnail-final.jpg")]).match(/\d+/g)!.slice(-2).join("x");
add("thumbnail-final.jpg", finalJpg === "3840x2160" && fs.statSync(A("thumbnail-final.jpg")).size < 2_000_000,
    `${finalJpg}, ${(fs.statSync(A("thumbnail-final.jpg")).size / 1e6).toFixed(2)} MB`);

const title = fs.readFileSync(A("youtube-title.txt"), "utf8").trim();
const description = fs.readFileSync(A("youtube-description.txt"), "utf8").trim();
const lengthErrors = checkLengths(title, description);
add("title and description limits", lengthErrors.length === 0, lengthErrors.join("; ") || `title ${title.length}/100, description ${description.length}/5000`);
const urls = description.match(/https?:\/\/\S+/g) ?? [];
const allowed = new Set([manifest.project.repository.replace(/\.git$/, ""),
                         ...Object.values(VERIFIED_SOURCES).map((x) => x.url)]);
const badLinks = urls.filter((u) => !allowed.has(u)).concat(/TODO|TBD|\[link\]|example\.com/i.test(description) ? ["placeholder text"] : []);
add("links", badLinks.length === 0, badLinks.length ? `unverified or placeholder: ${badLinks.join(", ")}` : `only verified links: ${urls.join(", ")}`);
const claimErrors = [...checkClaims(title, mode), ...checkClaims(description, mode)];
if (mode !== "live" && mode !== "replay" && /NVIDIA|Nebius/i.test(title)) claimErrors.push("title names NVIDIA/Nebius but the model was not called");
if (mode !== "live" && mode !== "replay" && !/not called/i.test(description)) claimErrors.push("description must say that the model was not called");
add("claims vs evidence", claimErrors.length === 0, claimErrors.join("; ") || `consistent with inference mode "${mode}" and measured results`);

const timeline = readJson(A("timeline.json"));
const duration = Number(ffprobe(video).format.duration);
const chapters: Chapter[] = timeline.chapters;
const chErrors = validateChapters(chapters, duration);
const text = fs.readFileSync(A("youtube-chapters.txt"), "utf8").trim().split("\n");
const sync = Math.abs(timeline.duration_seconds - duration) < 0.05 && timeline.sha256 && text.length === chapters.length &&
  chapters.every((c, i) => description.includes(text[i]));
add("chapters", chErrors.length === 0 && sync, chErrors.join("; ") || `${chapters.length} chapters, first 00:00, each >= 10 s, ` +
    `in the description, timeline matches the rendered ${duration.toFixed(2)} s file`);
const hashtags = description.match(/#\w+/g) ?? [];
add("hashtags", hashtags.length <= 3, `${hashtags.length}: ${hashtags.join(" ")}`);
const final = manifest.output_kind === "final";
add("submission video", final, final ? "final video with live/recorded inference" : "preview (MOCK): not upload-ready as the final submission");

const ok = rows.filter((r) => r.name !== "submission video").every((r) => r.ok);
const md = ["# YouTube package validation", "", `Build \`${build.id}\`. Checked ${new Date().toISOString()}. Nothing was uploaded.`, "",
  `Package checks: **${ok ? "pass" : "FAIL"}**. Upload readiness: **${ok && final ? "ready" : "not ready"}**${final ? "" : " (the video is a preview without a live NVIDIA call)"}. YouTube publication: **not published**.`, "",
  "| Check | Result | Detail |", "|---|---|---|", ...rows.map((r) => `| ${r.name} | ${r.ok ? "pass" : "FAIL"} | ${r.detail} |`), "",
  "Limits verified on YouTube Help (2026-10-28): title 100 characters, description 5,000 characters; chapters start at 00:00, at least three, ascending, each at least 10 seconds; thumbnails 16:9, JPG/PNG, up to 2 MB on mobile.", ""];
fs.writeFileSync(A("youtube-package-validation.md"), md.join("\n"));
for (const r of rows) console.log(`${r.ok ? "pass" : "FAIL"}  ${r.name}: ${r.detail}`);
process.exitCode = ok ? 0 : 1;
