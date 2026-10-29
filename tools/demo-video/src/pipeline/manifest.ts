// evidence_manifest: what was captured, from which commit, with which inference mode. Redacted by construction.
import { execFileSync } from "node:child_process";

export type InferenceInfo = { mode: "live" | "replay" | "mock" | "rules" | "unknown"; model_id?: string; latency_ms?: number };

export function inferenceFromText(text: string): InferenceInfo {
  const t = text.trim();
  let m = t.match(/^AI model (\S+) on Nebius Token Factory \(live call, ([\d.]+) s\)/);
  if (m) return { mode: "live", model_id: m[1], latency_ms: Math.round(Number(m[2]) * 1000) };
  m = t.match(/^AI model (\S+) \(recorded inference\)/);
  if (m) return { mode: "replay", model_id: m[1] };
  m = t.match(/^Test double (\S+)/);
  if (m) return { mode: "mock", model_id: m[1] };
  if (t.startsWith("Fixed rules")) return { mode: "rules" };
  return { mode: "unknown" };
}

export function outputKind(inferences: { mode: string }[]): "final" | "preview-mock" {
  return inferences.length > 0 && inferences.every((i) => i.mode === "live" || i.mode === "replay")
    ? "final" : "preview-mock";
}

const SECRET_KEY = /(api[_-]?key|authorization|secret|password|access[_-]?code|token)$/i;
const SECRET_VALUE = /(Bearer\s+\S+|cekbao_session=|\bv1\.[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{16,})/;

export function assertNoSecrets(value: unknown, path = "$"): void {
  if (value === null || value === undefined) return;
  if (typeof value === "string") {
    if (SECRET_VALUE.test(value)) throw new Error(`secret-like value at ${path}`);
    return;
  }
  if (Array.isArray(value)) { value.forEach((v, i) => assertNoSecrets(v, `${path}[${i}]`)); return; }
  if (typeof value === "object") {
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (SECRET_KEY.test(k) && k !== "tokens" && !k.endsWith("_tokens")) throw new Error(`secret-like key at ${path}.${k}`);
      assertNoSecrets(v, `${path}.${k}`);
    }
  }
}

export function gitState(repoRoot: string): { commit: string; dirty: boolean; changed_files: number } {
  const run = (args: string[]) => execFileSync("git", args, { cwd: repoRoot, encoding: "utf8" }).trim();
  const status = run(["status", "--porcelain"]);
  return { commit: run(["rev-parse", "HEAD"]), dirty: status.length > 0,
           changed_files: status ? status.split("\n").length : 0 };
}
