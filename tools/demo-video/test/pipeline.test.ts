// Pipeline logic tests (node:test). Run: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { validateConfig } from "../src/pipeline/config.ts";
import { splitIntoCues, toSrt, validateCues, wrapCaption } from "../src/pipeline/captions.ts";
import { buildTimeline, checkDuration } from "../src/pipeline/timeline.ts";
import { assertNoSecrets, inferenceFromText, outputKind } from "../src/pipeline/manifest.ts";
import { checkProbe, checkYoutubeRecommended, hasEditList, maxKeyframeGap, moovBeforeMdat } from "../src/pipeline/validate.ts";
import { assertCaptureComplete } from "../src/pipeline/capture-markers.ts";

const RAW = {
  video: { width: 1920, height: 1080, fps: 30, duration_target_seconds: 150, duration_limit_seconds: 300,
           language: "en", subtitles: "en", output: "artifacts/demo/cekbao-demo.mp4" },
  capture: { base_url: "env:DEMO_BASE_URL", port: 8790, data: "synthetic", inference: "live", max_paid_calls: 3,
             max_cost_usd: null },
};

test("config: accepts the brief's configuration", () => {
  const r = validateConfig(RAW);
  assert.deepEqual(r.errors, []);
  assert.equal(r.config?.video.fps, 30);
});

test("config: rejects real data, a target above the limit and too many paid calls", () => {
  const bad = structuredClone(RAW) as any;
  bad.capture.data = "production";
  bad.video.duration_target_seconds = 400;
  bad.capture.max_paid_calls = 10;
  bad.video.output = "out.mov";
  const r = validateConfig(bad);
  assert.equal(r.config, undefined);
  for (const word of ["synthetic", "limit", "max_paid_calls", ".mp4"]) {
    assert.ok(r.errors.some((e) => e.includes(word)), `missing error about ${word}: ${r.errors}`);
  }
});

test("captions: wrap to at most two lines within the character limit", () => {
  const lines = wrapCaption("The account in the instruction is not the account in the policy.", 42);
  assert.ok(lines.length <= 2 && lines.every((l) => l.length <= 42));
});

test("captions: long narration splits into several non-overlapping cues", () => {
  const text = "CEKBAO compares the instruction with the payment policy that applies on the payment date. " +
    "It never moves money. It never says that a payment is safe. It shows the source and the version it used.";
  const cues = splitIntoCues({ text, start: 10, end: 22 }, 42);
  assert.ok(cues.length >= 3);
  assert.deepEqual(validateCues(cues, 42), []);
  assert.equal(cues[0].start, 10);
  assert.equal(cues.at(-1)!.end, 22);
});

test("captions: validation reports overlaps, three-line cues and flashes", () => {
  const errors = validateCues([
    { start: 0, end: 2, lines: ["a", "b", "c"] },
    { start: 1.5, end: 1.8, lines: ["d"] },
  ], 42);
  assert.ok(errors.some((e) => e.includes("overlap")));
  assert.ok(errors.some((e) => e.includes("lines")));
  assert.ok(errors.some((e) => e.includes("short")));
});

test("captions: version numbers and links are not split as sentence ends", () => {
  const cues = splitIntoCues({ text: "Version 2025.1 applied until 31 August. Code: github.com/ghazyachmed/cekbao.", start: 0, end: 8 }, 44);
  const shown = cues.map((c) => c.lines.join(" ")).join(" ");
  assert.match(shown, /2025\.1 applied/);
  assert.match(shown, /github\.com\/ghazyachmed/);
});

test("captions: a long sentence is split into balanced cues, never a one-word orphan", () => {
  for (const text of ["CEKBAO compares the instruction with the institution's own policy, for the day you pay.",
                      "In Singapore, police reported at least 20 cases of scams impersonating schools since March 2026."]) {
    const cues = splitIntoCues({ text, start: 0, end: 6 }, 44);
    assert.deepEqual(validateCues(cues, 44), []);
    for (const c of cues) assert.ok(c.lines.join(" ").length >= 24, `orphan cue: "${c.lines.join(" ")}"`);
  }
});

test("captions: SRT timestamps", () => {
  const srt = toSrt([{ start: 61.5, end: 63.25, lines: ["Hello", "world"] }]);
  assert.equal(srt, "1\n00:01:01,500 --> 00:01:03,250\nHello\nworld\n");
});

test("timeline: scenes never cut narration and frames add up", () => {
  const t = buildTimeline([
    { id: "problem", videoSeconds: 0, narrationSeconds: 10.2, padSeconds: 1 },
    { id: "conflict", videoSeconds: 50, narrationSeconds: 40, padSeconds: 1 },
  ], 30);
  assert.equal(t.scenes[0].durationInFrames, Math.ceil(11.2 * 30));
  assert.equal(t.scenes[1].from, t.scenes[0].durationInFrames);
  assert.equal(t.totalFrames, t.scenes[0].durationInFrames + t.scenes[1].durationInFrames);
});

test("timeline: duration check fails above the official limit", () => {
  assert.equal(checkDuration(301, 150, 300).withinLimit, false);
  assert.equal(checkDuration(170, 150, 300).withinLimit, true);
  assert.equal(checkDuration(170, 150, null).withinLimit, true);
});

test("manifest: reads the inference mode from the result page, never from configuration", () => {
  assert.deepEqual(inferenceFromText("AI model nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B on Nebius Token Factory (live call, 1.8 s)"),
    { mode: "live", model_id: "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", latency_ms: 1800 });
  assert.equal(inferenceFromText("Fixed rules (no AI model call)").mode, "rules");
  assert.equal(inferenceFromText("Test double test/x (not a real model call)").mode, "mock");
  assert.equal(inferenceFromText("AI model nvidia/x (recorded inference)").mode, "replay");
  assert.equal(inferenceFromText("something else").mode, "unknown");
});

test("manifest: final output only when every scenario used live or recorded inference", () => {
  assert.equal(outputKind([{ mode: "live" }, { mode: "replay" }]), "final");
  assert.equal(outputKind([{ mode: "live" }, { mode: "rules" }]), "preview-mock");
  assert.equal(outputKind([]), "preview-mock");
});

test("manifest: secrets are refused", () => {
  assert.throws(() => assertNoSecrets({ headers: { Authorization: "Bearer abc" } }), /secret/);
  assert.throws(() => assertNoSecrets({ note: "cekbao_session=xyz" }), /secret/);
  assert.throws(() => assertNoSecrets({ nebius_api_key: "v1.abc" }), /secret/);
  assert.doesNotThrow(() => assertNoSecrets({ model_id: "nvidia/x", latency_ms: 10 }));
});

const PROBE = {
  streams: [
    { codec_type: "video", codec_name: "h264", pix_fmt: "yuv420p", width: 1920, height: 1080, r_frame_rate: "30/1" },
    { codec_type: "audio", codec_name: "aac", sample_rate: "48000", channels: 2 },
  ],
  format: { duration: "151.2" },
};

test("validate: a conforming MP4 passes every probe check", () => {
  const checks = checkProbe(PROBE, { width: 1920, height: 1080, fps: 30, limit: 300, expectAudio: true });
  assert.deepEqual(checks.filter((c) => !c.ok), []);
});

test("validate: wrong codec, resolution, missing audio and over-limit duration fail", () => {
  const bad = structuredClone(PROBE);
  bad.streams[0].codec_name = "vp9";
  bad.streams[0].width = 1280;
  bad.streams.pop();
  bad.format.duration = "301";
  const failed = checkProbe(bad, { width: 1920, height: 1080, fps: 30, limit: 300, expectAudio: true })
    .filter((c) => !c.ok).map((c) => c.name);
  assert.deepEqual(failed.sort(), ["audio", "duration", "resolution", "video_codec"].sort());
});

const YT = {
  streams: [
    { codec_type: "video", codec_name: "h264", profile: "High", bit_rate: "9800000", color_primaries: "bt709",
      color_transfer: "bt709", color_space: "bt709", field_order: "progressive" },
    { codec_type: "audio", codec_name: "aac", profile: "LC", bit_rate: "384000", sample_rate: "48000", channels: 2 },
  ],
  format: { duration: "224.1" },
};

test("validate: YouTube recommended upload settings pass for a conforming file", () => {
  assert.deepEqual(checkYoutubeRecommended(YT, { height: 1080, fps: 30, keyframeGap: 15, editList: false })
    .filter((c) => !c.ok), []);
});

test("validate: low bitrate, sRGB transfer, low audio bitrate, long GOP and edit lists are reported", () => {
  const bad = structuredClone(YT);
  bad.streams[0].bit_rate = "1985701";
  bad.streams[0].color_transfer = "iec61966-2-1";
  bad.streams[1].bit_rate = "317375";
  const failed = checkYoutubeRecommended(bad, { height: 1080, fps: 30, keyframeGap: 250, editList: true })
    .filter((c) => !c.ok).map((c) => c.name).sort();
  assert.deepEqual(failed, ["yt_audio_bitrate", "yt_color_bt709", "yt_edit_list", "yt_gop", "yt_video_bitrate"]);
});

test("validate: keyframe gap and edit-list detection", () => {
  assert.equal(maxKeyframeGap([1, 0, 0, 1, 0, 0, 0, 1]), 4);
  const atom = (type: string, body = Buffer.alloc(0)) => { const b = Buffer.alloc(8); b.writeUInt32BE(8 + body.length, 0); b.write(type, 4); return Buffer.concat([b, body]); };
  const withElst = Buffer.concat([atom("ftyp"), atom("moov", atom("trak", atom("edts", atom("elst")))), atom("mdat")]);
  assert.equal(hasEditList(withElst), true);
  assert.equal(hasEditList(Buffer.concat([atom("ftyp"), atom("moov", atom("trak")), atom("mdat")])), false);
});

test("validate: faststart means the moov atom comes before mdat", () => {
  const atom = (type: string, size = 16) => { const b = Buffer.alloc(size); b.writeUInt32BE(size, 0); b.write(type, 4); return b; };
  assert.equal(moovBeforeMdat(Buffer.concat([atom("ftyp"), atom("moov"), atom("mdat")])), true);
  assert.equal(moovBeforeMdat(Buffer.concat([atom("ftyp"), atom("mdat"), atom("moov")])), false);
});

test("capture: a run with missing steps is rejected instead of rendered", () => {
  const markers = [{ label: "form_filled", t: 1 }, { label: "submitted", t: 2 }];
  assert.throws(() => assertCaptureComplete("conflict", markers, ["form_filled", "submitted", "result_shown"]),
    /result_shown/);
  assert.doesNotThrow(() => assertCaptureComplete("conflict", [...markers, { label: "result_shown", t: 3 }],
    ["form_filled", "submitted", "result_shown"]));
});
