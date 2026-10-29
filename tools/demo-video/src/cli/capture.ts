// demo:capture: start the real app (or use DEMO_BASE_URL), record the three scenarios, write the redacted
// evidence manifest. Each run writes a new build directory; earlier captures are never overwritten.
import fs from "node:fs";
import path from "node:path";
import { loadConfig, resolveBaseUrl } from "../pipeline/config.ts";
import { captureScenario, launch, type ScenarioCapture } from "../pipeline/capture.ts";
import { assertNoSecrets, gitState, inferenceFromText, outputKind } from "../pipeline/manifest.ts";
import { SCENARIOS, seed } from "../pipeline/scenarios.ts";
import { ARTIFACTS, REPO, TOOL_DIR, buildId, readJson, run, startApp, stopApp, waitForDown, waitForReady, writeJson } from "../pipeline/util.ts";

const cfg = loadConfig(path.join(TOOL_DIR, "demo.config.json"));
const git = gitState(REPO);
const id = buildId(git.commit);
const dir = path.join(ARTIFACTS, "raw", id);
fs.mkdirSync(dir, { recursive: true });
console.log(`capture ${id}`);
console.log(seed());

const external = resolveBaseUrl(cfg.capture);
const baseUrl = external ?? `http://127.0.0.1:${cfg.capture.port}`;
const dbPath = path.join(dir, "app-demo.sqlite3"), appLog = path.join(dir, "app.log");
// The rehearsal runs on an app with paid inference switched off (PG_MAX_PAID_CALLS=0 overrides .env.local), so only
// the recorded run spends model calls: three scenario checks, within the approved budget ledger.
let app = external ? null : startApp(cfg.capture.port, dbPath, appLog, { PG_MAX_PAID_CALLS: "0" });
const captures: ScenarioCapture[] = [];
const startedAt = new Date().toISOString();
try {
  await waitForReady(baseUrl);
  const browser = await launch();
  try {
    // Rehearse every scenario without recording; any missing selector or failed assertion aborts the run.
    let rehearsalCase = "";
    for (const s of SCENARIOS) {
      const r = await captureScenario(browser, baseUrl, s, dir, { record: false, caseRef: rehearsalCase });
      if (s.key === "insufficient") rehearsalCase = r.case_path.split("/").pop()!;
      console.log(`  rehearsal ${s.key}: ok`);
    }
    if (app) {                             // restart with the configured inference settings for the recording
      stopApp(app);
      await waitForDown(baseUrl);
      app = startApp(cfg.capture.port, dbPath, appLog);
      await waitForReady(baseUrl);
    }
    let insufficientCase = "";
    for (const s of SCENARIOS) {           // one scenario at a time: bounded concurrency and cost
      const c = await captureScenario(browser, baseUrl, s, dir, { record: true, caseRef: insufficientCase });
      if (s.key === "insufficient") insufficientCase = c.case_path.split("/").pop()!;
      console.log(`  ${s.code} ${s.key}: ${c.headlines.join(" / ")}${c.inference_text ? `; read by: ${c.inference_text}` : ""}`);
      captures.push(c);
    }
  } finally {
    await browser.close();
  }
} finally {
  if (app) stopApp(app);
  fs.rmSync(path.join(dir, "tmp-video"), { recursive: true, force: true });
}

const checked = captures.filter((c) => c.key !== "escalation");
const inferences = checked.map((c) => ({ scenario: c.key, ...inferenceFromText(c.inference_text),
  tokens: c.inference_text.match(/(\d+) input and (\d+) output tokens/)?.slice(1).join(" in / ") + " out" || null }));
const kind = outputKind(inferences);
const envFile = path.join(REPO, ".env.local");
const envText = fs.existsSync(envFile) ? fs.readFileSync(envFile, "utf8") : "";
const configured = (k: string) => Boolean(process.env[k]) || new RegExp(`^${k}=.+`, "m").test(envText);
const missing = ["NEBIUS_API_KEY", "NEBIUS_MODEL_ID", "PG_INFERENCE_BUDGET_USD", "PG_MAX_PAID_CALLS"].filter((k) => !configured(k));
const pytest = run(".venv/bin/python", ["-m", "pytest", "-q"]).match(/(\d+) passed/);
const audit = readOptional(path.join(REPO, "evidence/policyguard/ui/audit-summary.json"));
const lh = readOptional(path.join(REPO, "evidence/policyguard/ui/lighthouse/summary.json"));
const liveDir = path.join(REPO, "evidence/policyguard/nebius_live");
const liveRecords = fs.existsSync(liveDir) ? fs.readdirSync(liveDir).filter((f) => f.endsWith(".json")).sort() : [];
const primary = inferences.find((i) => i.scenario === "conflict") ?? inferences[0];
const manifest = {
  schema: "cekbao-demo-evidence/1",
  build_id: id,
  captured_at: startedAt,
  git,
  app: { base_url: baseUrl.replace(/\/\/[^/]*@/, "//"), started_by_pipeline: !app ? false : true,
         data: "synthetic (policyguard/seed.py)" },
  official_rules: cfg.rules_source,
  scenarios: captures.map((c) => ({ code: c.code, key: c.key, title: c.title, case_ref: c.case_path.split("/").pop(),
    headlines: c.headlines, status_seen_after_submit: c.status_seen, evidence_sources: c.evidence_titles,
    inference: inferences.find((i) => i.scenario === c.key) ?? null, video: c.video, markers: c.markers })),
  inference_summary: {
    provider: "nebius", mode: kind === "final" ? (inferences.every((i) => i.mode === "live") ? "live" : "replay") : primary.mode,
    model_id: primary.model_id ?? null, latency_ms: primary.latency_ms ?? null, tokens: primary.tokens,
    checked_at: startedAt, per_scenario: inferences,
    blocked_reason: kind === "final" ? null : missing.length
      ? `not configured at capture time: ${missing.join(", ")}` : "the app did not report a live model call",
    live_check_records: liveRecords.map((f) => `evidence/policyguard/nebius_live/${f}`),
  },
  output_kind: kind,
  measurements: {
    tests_passed: pytest ? Number(pytest[1]) : null,
    axe_violations: audit ? audit.results.reduce((n: number, r: any) => n + (r.axe_violations?.length ?? 0), 0) : null,
    axe_audit: audit ? { generated_at: audit.generated_at, pages: new Set(audit.results.map((r: any) => r.page)).size } : null,
    lighthouse_accessibility_min: lh ? Math.min(...lh.map((x: any) => x.accessibility)) : null,
  },
  project: { repository: run("git", ["remote", "get-url", "origin"]).trim() },
};
assertNoSecrets(manifest);
writeJson(path.join(dir, "capture.json"), { build_id: id, scenarios: captures });
writeJson(path.join(dir, "evidence-manifest.json"), manifest);
writeJson(path.join(ARTIFACTS, "raw", "latest.json"), { id });
console.log(`output kind: ${kind}${kind === "final" ? "" : ` (${manifest.inference_summary.blocked_reason})`}`);
console.log(`capture stored in ${path.relative(REPO, dir)}`);

function readOptional(file: string): any {
  return fs.existsSync(file) ? readJson(file) : null;
}
