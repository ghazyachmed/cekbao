// demo:doctor: dependencies, configuration, services and app access. Exit 1 when a blocking check fails.
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
import { loadConfig, resolveBaseUrl } from "../pipeline/config.ts";
import { KokoroLocalTts } from "../pipeline/tts.ts";
import { NPX_REMOTION, REPO, TOOL_DIR, run } from "../pipeline/util.ts";

type Row = [string, boolean, string, boolean];   // name, ok, detail, blocking
const rows: Row[] = [];
const check = (name: string, blocking: boolean, fn: () => string) => {
  try { rows.push([name, true, fn(), blocking]); } catch (e) { rows.push([name, false, String((e as Error).message).split("\n")[0], blocking]); }
};

check("node >= 25", true, () => { if (Number(process.versions.node.split(".")[0]) < 25) throw new Error(process.version); return process.version; });
check("config", true, () => { const c = loadConfig(path.join(TOOL_DIR, "demo.config.json")); return `${c.video.width}x${c.video.height}@${c.video.fps}, target ${c.video.duration_target_seconds}s, limit ${c.video.duration_limit_seconds}s`; });
check("remotion cli", true, () => run(NPX_REMOTION, ["versions"], { cwd: TOOL_DIR }).match(/remotion\S*\s+(\S+)/)?.[1] ?? "installed");
check("google chrome (playwright channel)", true, () => { const p = chromium.executablePath(); return fs.existsSync("/Applications/Google Chrome.app") ? "installed" : (p || "missing"); });
check("playwright ffmpeg (video recording)", true, () => {
  const dir = path.join(process.env.HOME ?? "", "Library/Caches/ms-playwright");
  const f = fs.readdirSync(dir).filter((d) => d.startsWith("ffmpeg-"));
  if (!f.length) throw new Error("run: npx playwright install ffmpeg");
  return f.join(", ");
});
check("python venv (.venv)", true, () => run(".venv/bin/python", ["--version"]).trim());
check("postgres + redis (local)", true, () => run("scripts/policyguard_local.sh", ["status"]).replace(/\n/g, "; ").trim());
check("swift (frame QA)", false, () => run("swift", ["--version"]).split("\n")[0]);
check("kokoro tts (local, optional)", false, () => { if (!KokoroLocalTts.available()) throw new Error("not installed; video will have captions only"); return "available"; });
check("nebius live inference", false, () => {
  const env = fs.existsSync(path.join(REPO, ".env.local")) ? fs.readFileSync(path.join(REPO, ".env.local"), "utf8") : "";
  const has = (k: string) => Boolean(process.env[k]) || new RegExp(`^${k}=.+`, "m").test(env);
  const missing = ["NEBIUS_API_KEY", "NEBIUS_MODEL_ID", "PG_INFERENCE_BUDGET_USD", "PG_MAX_PAID_CALLS"].filter((k) => !has(k));
  if (missing.length) throw new Error(`not configured (${missing.join(", ")}); output will be a MOCK preview`);
  return "configured (values not shown)";
});
check("disk space >= 2 GB", true, () => {
  const free = Number(run("df", ["-k", REPO]).split("\n")[1].split(/\s+/)[3]) * 1024;
  if (free < 2e9) throw new Error(`${(free / 1e9).toFixed(1)} GB free`);
  return `${(free / 1e9).toFixed(0)} GB free`;
});
const cfg = loadConfig(path.join(TOOL_DIR, "demo.config.json"));
const base = resolveBaseUrl(cfg.capture);
if (base) {
  try {
    const r = await fetch(`${base}/readyz`);
    rows.push(["app access", r.ok, `${base}/readyz -> ${r.status}`, true]);
  } catch (e) { rows.push(["app access", false, `${base}: ${(e as Error).message}`, true]); }
} else rows.push(["app access", true, `DEMO_BASE_URL unset: capture starts the app on port ${cfg.capture.port}`, true]);

for (const [name, ok, detail, blocking] of rows) console.log(`${ok ? "ok  " : blocking ? "FAIL" : "warn"}  ${name}: ${detail}`);
process.exitCode = rows.some(([, ok, , blocking]) => !ok && blocking) ? 1 : 0;
