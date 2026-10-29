// demo:gallery: Devpost image gallery (3:2, 1800x1200 JPG, < 5 MB each) as editable Remotion Stills.
// App images are real captures from the latest build (synthetic data); numbers come from the evidence manifest.
import fs from "node:fs";
import path from "node:path";
import type { ScenarioCapture } from "../pipeline/capture.ts";
import type { GalleryImage, GalleryProps } from "../remotion/Gallery.tsx";
import { V } from "../remotion/theme.ts";
import { ARTIFACTS, NPX_REMOTION, PUBLIC_BUILD, TOOL_DIR, latestBuild, readJson, run, writeJson } from "../pipeline/util.ts";

const build = latestBuild();
const capture = readJson(path.join(build.dir, "capture.json"));
const m = readJson(path.join(build.dir, "evidence-manifest.json")).measurements;
const assets = path.join(PUBLIC_BUILD, build.id);
fs.mkdirSync(assets, { recursive: true });
const out = path.join(ARTIFACTS, "gallery");
fs.mkdirSync(out, { recursive: true });

/** A still from the capture, copied next to the Remotion assets; width and height in CSS px. */
function still(scenario: string, name: string): GalleryImage {
  const cap = capture.scenarios.find((s: ScenarioCapture) => s.key === scenario) as ScenarioCapture;
  const st = cap.stills.find((s) => s.name === name);
  if (!st) throw new Error(`gallery: still ${scenario}/${name} missing in build ${build.id}`);
  fs.copyFileSync(path.join(build.dir, st.file), path.join(assets, st.file));
  return { src: `build/${build.id}/${st.file}`, w: st.width, h: st.height };
}

type Slide = Omit<GalleryProps, "index" | "total"> & { slug: string };
const slides: Slide[] = [
  { slug: "cover", accent: V.coral, title: "Check a payment instruction before you pay",
    caption: "CEKBAO compares a payment request with the payment policy the institution published for the date you pay.",
    phones: [still("policy_change", "mobile"), still("conflict", "mobile"), still("insufficient", "mobile")] },
  { slug: "result-first", accent: V.coral, title: "The result and the next step come first",
    caption: "Four fixed labels: matches, conflicts, not enough evidence, institution review required. Never “safe to pay”.",
    images: [still("conflict", "result_shown"), still("conflict", "next_action_shown")] },
  { slug: "detail-by-detail", accent: V.coral, title: "Detail by detail: the instruction against the policy",
    caption: "Each detail shows what the instruction asks for, what the policy states, and whether they agree.",
    images: [still("conflict", "explanation_shown")] },
  { slug: "policy-versions", accent: V.violet, title: "The payment date chooses the policy version",
    caption: "The same invoice conflicts on 30 November (policy 2026.1) and matched on 14 August (policy 2025.1).",
    images: [still("policy_change", "result_shown"), still("policy_change", "earlier_payment_shown")] },
  { slug: "evidence-authority", accent: V.amber, title: "Evidence needs an authorized publisher",
    caption: "An agent's page is not enough. The French original stays visible; the translation is labelled unofficial.",
    images: [still("insufficient", "explanation_shown"), still("insufficient", "evidence_shown")] },
  { slug: "how-it-works", accent: V.green, title: "How it works: NVIDIA Nemotron reads, rules decide",
    caption: "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B on Nebius Token Factory proposes fields; code and rules do the rest.",
    steps: [["Check saved", "HTTP 202 after the database commit; a transactional outbox queues the job."],
            ["Worker leases the job", "Leases with heartbeat, retries with jitter, dead letters, idempotency."],
            ["Nemotron on Nebius", "Strict JSON schema, temperature 0; every field needs a verbatim quote."],
            ["Quote check in code", "Fields whose quote is not in the instruction are dropped."],
            ["Rules decide", "The policy version valid on the payment date, the issuer's authority, the result."]] },
  { slug: "tested", accent: V.teal, title: "Measured on this build",
    caption: "Local measurements with synthetic data. No user testing yet; a policy match is not a payment confirmation.",
    stats: [[String(m.tests_passed), "automated tests pass (pytest, Hypothesis)"],
            [String(m.axe_violations), `axe-core WCAG violations on ${m.axe_audit?.pages ?? "the"} audited pages`],
            [String(m.lighthouse_accessibility_min), "lowest Lighthouse accessibility score (lab)"],
            ["≤ 3 ms", "per query on 100,000 synthetic cases (EXPLAIN ANALYZE, local)"]] },
];

const sizes: Record<string, number> = {};
slides.forEach((s, i) => {
  const { slug, ...rest } = s;
  const props: GalleryProps = { ...rest, index: i + 1, total: slides.length };
  const name = `${String(i + 1).padStart(2, "0")}-${slug}`;
  const propsFile = path.join(out, `${name}.props.json`);
  writeJson(propsFile, props);
  const file = path.join(out, `${name}.jpg`);
  run(NPX_REMOTION, ["still", path.join(TOOL_DIR, "src/remotion/index.ts"), "Gallery", file, `--props=${propsFile}`,
                     "--image-format=jpeg", "--jpeg-quality=90", "--log=error"], { cwd: TOOL_DIR });
  sizes[name] = fs.statSync(file).size;
  if (sizes[name] >= 5_000_000) throw new Error(`${name}.jpg is ${sizes[name]} bytes (Devpost limit 5 MB)`);
});
writeJson(path.join(out, "gallery.json"), { build_id: build.id, size: "1800x1200 (3:2)", files: sizes });
console.log(JSON.stringify(sizes));
