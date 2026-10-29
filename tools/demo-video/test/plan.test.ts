// Composition plan tests: animated scenes, callouts and sound effects. Run: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildScript, type Facts } from "../src/pipeline/narration.ts";
import { makePlan, SCENE_ORDER } from "../src/pipeline/plan.ts";

const ANCHORS: Record<string, string[]> = {
  conflict: ["form_open", "form_filled", "institution_shown", "dates_shown", "submitted", "result_shown",
             "next_action_shown", "explanation_shown", "evidence_shown", "inference_shown"],
  policy_change: ["form_filled", "dates_shown", "result_shown", "explanation_shown", "earlier_payment_shown"],
  insufficient: ["submitted", "result_shown", "explanation_shown", "evidence_shown"],
  escalation: ["queue_shown", "review_case_shown", "review_recorded"],
};
const HEADLINES: Record<string, string[]> = {
  conflict: ["Conflicts with the checked policy."],
  policy_change: ["Conflicts with the checked policy.", "Matches the checked policy."],
  insufficient: ["Not enough evidence to verify."], escalation: ["Not enough evidence to verify."],
};
const captures = Object.fromEntries(Object.entries(ANCHORS).map(([key, anchors]) => [key, {
  key, code: key === "conflict" ? "A" : key === "policy_change" ? "B" : "C", title: key, headlines: HEADLINES[key],
  video: `${key}.webm`, viewport: { width: 1440, height: 810 }, inference_text: "Fixed rules (no AI model call)",
  markers: [...anchors.map((label, i) => ({ label, t: 1 + i * 2, ...(i === 1 ? { at: { x: 100, y: 200 } } : {}) })),
            { label: "end", t: 1 + anchors.length * 2 }],
  stills: [{ name: "result_shown", file: `${key}-result_shown.png`, width: 600, height: 200 },
           { name: "mobile", file: `${key}-mobile.png`, width: 390, height: 844 }],
}])) as any;
const FACTS: Facts = { inferenceMode: "rules", modelId: null, latencySeconds: null, testsPassed: 230, axeViolations: 0,
                       repoUrl: "https://github.com/ghazyachmed/cekbao" };

function plan(facts = FACTS) {
  const lines = buildScript(captures, facts);
  const voiced = lines.map((l) => ({ id: l.id, file: `/tmp/${l.id}.wav`, seconds: 2.5 }));
  return { lines, plan: makePlan(lines, voiced, captures, "build/x", 30, {}) };
}

test("an animated problem intro opens the video and a real app screen appears within 15 seconds", () => {
  const { plan: p } = plan();
  const intro = p.scenes[0];
  assert.equal(intro.id, "intro");
  assert.equal(intro.teaser?.src, "build/x/conflict-mobile.png");   // a real phone capture of the app, not a drawing
  assert.ok(p.productFrame / p.fps <= 15, `app first visible at ${p.productFrame / p.fps} s`);
  assert.equal(p.productFrame, intro.from + intro.beats![1]);
});

test("the policy timeline follows scenario B and its animation beats follow the narration", () => {
  const { plan: p, lines } = plan();
  const i = SCENE_ORDER.indexOf("policy_timeline");
  assert.equal(SCENE_ORDER[i - 1], "policy_change");
  const scene = p.scenes.find((s) => s.id === "policy_timeline")!;
  const said = lines.filter((l) => l.scene === "policy_timeline");
  assert.equal(scene.beats?.length, said.length);
  assert.ok(scene.beats!.every((b, k) => b >= 0 && b < scene.durationInFrames && (k === 0 || b > scene.beats![k - 1])));
});

test("every recorded segment carries a short callout; result callouts quote the app's own headline", () => {
  const { plan: p } = plan();
  for (const s of p.scenes) for (const seg of s.segments) {
    assert.ok(seg.callout && seg.callout.text.length > 0 && seg.callout.text.length <= 44, `${s.id}/${seg.label}`);
  }
  const result = p.scenes.find((s) => s.id === "insufficient")!.segments.find((g) => g.label === "result_shown")!;
  assert.equal(result.callout!.text, "Not enough evidence to verify");
  assert.equal(result.callout!.tone, "warn");
  const earlier = p.scenes.find((s) => s.id === "policy_change")!.segments.find((g) => g.label === "earlier_payment_shown")!;
  assert.equal(earlier.callout!.tone, "ok");
});

test("a callout stays only while its sentence is spoken, so later actions in the clip are not mislabelled", () => {
  const { plan: p } = plan();
  for (const s of p.scenes) for (const seg of s.segments) {
    const spoken = Math.ceil(2.5 * p.fps);
    assert.ok(seg.callout!.frames >= spoken, `${s.id}/${seg.label} callout shorter than its sentence`);
    assert.ok(seg.callout!.frames <= Math.min(seg.playFrames + seg.freezeFrames, spoken + p.fps), `${s.id}/${seg.label} callout too long`);
  }
});

test("in live mode the intro names NVIDIA Nemotron on Nebius; in a preview it does not claim it", () => {
  const live = buildScript(captures, { ...FACTS, inferenceMode: "live", modelId: "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", latencySeconds: 1.8 });
  assert.match(live.filter((l) => l.scene === "intro").map((l) => l.text).join(" "), /NVIDIA Nemotron on Nebius/);
  const preview = buildScript(captures, FACTS);
  assert.doesNotMatch(preview.filter((l) => l.scene === "intro").map((l) => l.text).join(" "), /Nemotron/);
});

test("the edit fits the three-minute judging window: no reviewer scene, short results", () => {
  assert.ok(!SCENE_ORDER.includes("escalation"));
  const { lines } = plan();
  assert.ok(lines.filter((l) => l.scene === "results").length <= 2);
  assert.ok(lines.filter((l) => l.scene === "nvidia").length <= 2);
});

test("the inference callout states what actually read the instruction", () => {
  const rules = plan().plan.scenes.find((s) => s.id === "conflict")!.segments.find((g) => g.label === "inference_shown")!;
  assert.match(rules.callout!.text, /not called/i);
  const live = plan({ ...FACTS, inferenceMode: "live", modelId: "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", latencySeconds: 1.8 })
    .plan.scenes.find((s) => s.id === "conflict")!.segments.find((g) => g.label === "inference_shown")!;
  assert.match(live.callout!.text, /Nemotron/);
});

test("sound effects stay quiet, inside the video, and out of the narration track", () => {
  const { plan: p } = plan();
  assert.ok(p.sfx.length >= SCENE_ORDER.length);
  for (const s of p.sfx) {
    assert.ok(s.from >= 0 && s.from + s.durationInFrames <= p.totalFrames, `sfx at ${s.from}`);
    assert.ok(s.volume > 0 && s.volume <= 0.5);
  }
  assert.ok(p.audio.every((a) => !a.src.includes("sfx")));
});
