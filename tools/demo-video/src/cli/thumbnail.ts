// demo:thumbnail: three editable Remotion Still variants built around a real phone capture of the app,
// 3840x2160 masters, JPGs < 2 MB, 320x180 / 160x90 previews. Uses the stored capture only.
import fs from "node:fs";
import path from "node:path";
import type { ScenarioCapture } from "../pipeline/capture.ts";
import type { HeadlineLine, ThumbnailProps } from "../remotion/Thumbnail.tsx";
import { V, type Tone } from "../remotion/theme.ts";
import { ARTIFACTS, NPX_REMOTION, PUBLIC_BUILD, REPO, TOOL_DIR, latestBuild, readJson, run, writeJson } from "../pipeline/util.ts";

// Each variant: three headline lines (one neon), the accent, the scenario whose phone capture fills the phone,
// and a large chip that restates the app's own result so it still reads at 160x90.
type Variant = { headline: string; lines: HeadlineLine[]; accent: string; scenario: string };
export const VARIANTS: Record<string, Variant> = {
  A: { headline: "Check before you pay", accent: V.coral, scenario: "conflict",
       lines: [{ text: "Check" }, { text: "before" }, { text: "you pay", neon: true }] },
  B: { headline: "Who authorized this?", accent: V.amber, scenario: "insufficient",
       lines: [{ text: "Who" }, { text: "authorized", neon: true }, { text: "this?" }] },
  C: { headline: "When policies change", accent: V.violet, scenario: "policy_change",
       lines: [{ text: "When" }, { text: "policies" }, { text: "change", neon: true }] },
};

/** Short, uppercase form of an app headline, with its tone ("Conflicts with the checked policy." -> CONFLICTS). */
export function chipFor(headline: string): { text: string; tone: Tone } {
  if (/^conflict/i.test(headline)) return { text: "CONFLICTS WITH POLICY", tone: "bad" };
  if (/^match/i.test(headline)) return { text: "MATCHES POLICY", tone: "ok" };
  if (/^not enough evidence/i.test(headline)) return { text: "NOT ENOUGH EVIDENCE", tone: "warn" };
  return { text: headline.replace(/\.$/, "").toUpperCase(), tone: "warn" };
}

const build = latestBuild();
const capture = readJson(path.join(build.dir, "capture.json"));
const out = path.join(ARTIFACTS, "thumbnails");
fs.mkdirSync(out, { recursive: true });
const assets = path.join(PUBLIC_BUILD, build.id);
fs.mkdirSync(assets, { recursive: true });
for (const [v, spec] of Object.entries(VARIANTS)) {
  const cap = capture.scenarios.find((s: ScenarioCapture) => s.key === spec.scenario) as ScenarioCapture;
  const still = cap.stills.find((s) => s.name === "mobile");
  if (!still) throw new Error(`thumbnail ${v}: phone capture missing in build ${build.id} (re-run demo:capture)`);
  fs.copyFileSync(path.join(build.dir, still.file), path.join(assets, still.file));
  const phone = { src: `build/${build.id}/${still.file}`, w: still.width, h: still.height };
  const [next, earlier] = cap.headlines;
  const props: ThumbnailProps = { lines: spec.lines, accent: spec.accent, phone, note: "REAL APP · SYNTHETIC DATA",
    ...(spec.scenario === "policy_change"
      ? { dates: [{ label: "14 AUG", result: chipFor(earlier).text.split(" ")[0], tone: chipFor(earlier).tone },
                  { label: "30 NOV", result: chipFor(next).text.split(" ")[0], tone: chipFor(next).tone }] }
      : { chip: chipFor(next) }) };
  const propsFile = path.join(out, `thumbnail-${v.toLowerCase()}.props.json`);
  writeJson(propsFile, props);
  run(NPX_REMOTION, ["still", path.join(TOOL_DIR, "src/remotion/index.ts"), `Thumbnail${v}`,
                     path.join(out, `thumbnail-${v.toLowerCase()}-master.png`), `--props=${propsFile}`, "--scale=2",
                     "--log=error"], { cwd: TOOL_DIR });
}
const sizes = JSON.parse(run(path.join(REPO, "video/.tts/venv/bin/python"),
                             [path.join(TOOL_DIR, "qa/thumbs.py"), out, ...Object.keys(VARIANTS)]));
writeJson(path.join(out, "thumbnails.json"), { build_id: build.id, variants: VARIANTS, sizes });
for (const v of Object.keys(VARIANTS)) fs.copyFileSync(path.join(out, `thumbnail-${v.toLowerCase()}.jpg`),
                                                       path.join(ARTIFACTS, `thumbnail-${v.toLowerCase()}.jpg`));
console.log(JSON.stringify(sizes));
