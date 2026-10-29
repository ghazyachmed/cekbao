// YouTube package logic tests. Run: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildChapters, checkClaims, checkLengths, chapterText, validateChapters } from "../src/pipeline/youtube.ts";

const scenes = [
  { id: "title_conflict", from: 0, durationInFrames: 78 }, { id: "conflict", from: 78, durationInFrames: 2100 },
  { id: "title_policy_change", from: 2178, durationInFrames: 60 }, { id: "policy_change", from: 2238, durationInFrames: 900 },
  { id: "title_insufficient", from: 3138, durationInFrames: 60 }, { id: "insufficient", from: 3198, durationInFrames: 600 },
  { id: "escalation", from: 3798, durationInFrames: 450 }, { id: "nvidia", from: 4248, durationInFrames: 420 },
  { id: "results", from: 4668, durationInFrames: 240 },
];

test("chapters start at 00:00, merge short scenes and cover the rendered duration", () => {
  const ch = buildChapters(scenes, 30, 4908 / 30, "rules");
  assert.equal(ch[0].start, 0);
  assert.ok(ch.length >= 3);
  assert.deepEqual(validateChapters(ch, 4908 / 30), []);
  assert.ok(ch.every((c, i) => i === 0 || c.start > ch[i - 1].start));
  assert.equal(chapterText(ch).split("\n")[0].slice(0, 5), "00:00");
});

test("a closing chapter shorter than 10 s is merged, never left alone", () => {
  const short = scenes.map((s) => (s.id === "results" ? { ...s, durationInFrames: 150 } : s));
  const ch = buildChapters(short, 30, (4668 + 150) / 30, "rules");
  assert.deepEqual(validateChapters(ch, (4668 + 150) / 30), []);
  assert.notEqual(ch.at(-1)!.title, "Results and limits");
});

test("the animated problem intro becomes the first chapter and the timeline joins the policy chapter", () => {
  const withIntro = [{ id: "intro", from: 0, durationInFrames: 810 },
    ...scenes.map((s) => ({ ...s, from: s.from + 810 })),
  ];
  withIntro.splice(5, 0, { id: "policy_timeline", from: 0, durationInFrames: 0 });
  const total = (4908 + 810) / 30;
  const ch = buildChapters(withIntro.filter((s) => s.durationInFrames), 30, total, "rules");
  assert.equal(ch[0].title, "The problem: a payment email with a new account");
  assert.equal(ch[1].start, 27);
  assert.deepEqual(validateChapters(ch, total), []);
});

test("chapter validation catches each rule", () => {
  const errors = validateChapters([{ start: 2, title: "a" }, { start: 8, title: "b" }], 15);
  assert.ok(errors.some((e) => e.includes("00:00")));
  assert.ok(errors.some((e) => e.includes("at least three")));
  assert.ok(errors.some((e) => e.includes("10 seconds")));
});

test("title and description limits", () => {
  assert.deepEqual(checkLengths("CEKBAO demo", "Short description."), []);
  assert.ok(checkLengths("x".repeat(101), "ok").some((e) => e.includes("100")));
  assert.ok(checkLengths("ok", "y".repeat(5001)).some((e) => e.includes("5000")));
  assert.ok(checkLengths("a <b>", "ok").some((e) => e.includes("angle")));
});

test("unsupported claims and mode mismatches fail", () => {
  assert.ok(checkClaims("CEKBAO makes it safe to pay", "rules").length > 0);
  assert.ok(checkClaims("Trusted by 40 universities", "rules").length > 0);
  assert.ok(checkClaims("Reduces fraud by 90%", "rules").length > 0);
  assert.ok(checkClaims("Live NVIDIA inference on Nebius", "rules").length > 0);
  assert.deepEqual(checkClaims("The NVIDIA model was not called in this preview.", "rules"), []);
  assert.deepEqual(checkClaims("Live call to NVIDIA Nemotron on Nebius, 1.8 s measured.", "live"), []);
});

test("a disclosure that denies a customer relationship is not a customer claim", () => {
  assert.deepEqual(checkClaims("All institutions are synthetic. They are not customers or partners.", "rules"), []);
  assert.ok(checkClaims("Used by customers in 12 countries", "rules").length > 0);
});
