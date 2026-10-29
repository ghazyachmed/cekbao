// Failure handling: missing voiceover files and captures without the markers the narration needs.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { UserVoiceover } from "../src/pipeline/tts.ts";
import { makePlan } from "../src/pipeline/plan.ts";

test("a user voiceover with a missing line fails loudly", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vo-"));
  assert.throws(() => new UserVoiceover(dir).synthesize([{ id: "conflict_1", scene: "conflict", text: "x" }],
                                                         path.join(dir, "out")), /voiceover file missing/);
});

test("a capture without the markers the narration anchors to is refused", () => {
  const capture = { key: "conflict", code: "A", title: "t", video: "conflict.webm", final_still: "f.png",
    markers: [{ label: "form_open", t: 1 }, { label: "end", t: 9 }], case_path: "/check/cases/x", headlines: ["h"],
    inference_text: "", stills: [], evidence_titles: [], status_seen: "", viewport: { width: 1440, height: 810 } };
  const lines = [{ id: "conflict_1", scene: "conflict", text: "a", anchor: "form_open" },
                 { id: "conflict_2", scene: "conflict", text: "b", anchor: "result_shown" }];
  const voiced = lines.map((l) => ({ id: l.id, file: null, seconds: 1 }));
  assert.throws(() => makePlan(lines, voiced, { conflict: capture } as any, "build/x", 30, {}), /result_shown/);
});
