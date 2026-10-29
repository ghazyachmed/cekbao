// Shared paths and process helpers.
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const TOOL_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const REPO = path.resolve(TOOL_DIR, "../..");
export const ARTIFACTS = path.join(REPO, "artifacts", "demo");
export const PUBLIC_BUILD = path.join(TOOL_DIR, "public", "build");
export const NPX_REMOTION = path.join(TOOL_DIR, "node_modules", ".bin", "remotion");

export function buildId(commit: string): string {
  return `${new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z")}-${commit.slice(0, 7)}`;
}

export function run(cmd: string, args: string[], opts: { cwd?: string; env?: NodeJS.ProcessEnv } = {}): string {
  return execFileSync(cmd, args, { cwd: opts.cwd ?? REPO, env: { ...process.env, ...opts.env }, encoding: "utf8",
                                   stdio: ["ignore", "pipe", "pipe"], maxBuffer: 64 * 1024 * 1024 });
}

export function writeJson(file: string, data: unknown): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
}

export function readJson<T = any>(file: string): T {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

export function latestBuild(): { id: string; dir: string } {
  const pointer = path.join(ARTIFACTS, "raw", "latest.json");
  if (!fs.existsSync(pointer)) throw new Error("No capture found. Run npm run demo:capture first.");
  const { id } = readJson<{ id: string }>(pointer);
  return { id, dir: path.join(ARTIFACTS, "raw", id) };
}

export async function waitForReady(baseUrl: string, timeoutMs = 60000): Promise<void> {
  const until = Date.now() + timeoutMs;
  let last = "";
  while (Date.now() < until) {
    try {
      const r = await fetch(`${baseUrl}/readyz`);
      if (r.ok) return;
      last = `HTTP ${r.status}`;
    } catch (e) { last = String(e); }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`App at ${baseUrl} not ready after ${timeoutMs} ms (${last})`);
}

export function startApp(port: number, dbPath: string, logFile: string, env: Record<string, string> = {}): ChildProcess {
  const out = fs.openSync(logFile, "a");
  return spawn(path.join(REPO, "scripts", "policyguard_serve.sh"), [String(port)], {
    cwd: REPO, detached: true, stdio: ["ignore", out, out], env: { ...process.env, CEKBAO_DB_PATH: dbPath, ...env } });
}

/** Waits until nothing answers on the base URL any more (after stopApp). */
export async function waitForDown(baseUrl: string, timeoutMs = 30000): Promise<void> {
  const until = Date.now() + timeoutMs;
  while (Date.now() < until) {
    try { await fetch(`${baseUrl}/readyz`); } catch { return; }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`App at ${baseUrl} still answering after ${timeoutMs} ms`);
}

export function stopApp(child: ChildProcess): void {
  if (child.pid) { try { process.kill(-child.pid, "SIGTERM"); } catch { /* already stopped */ } }
}

export function ffprobe(file: string): any {
  return JSON.parse(run(NPX_REMOTION, ["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
                                       "-show_streams", file], { cwd: TOOL_DIR }));
}

export function wavSeconds(file: string): number {
  const b = fs.readFileSync(file);
  const byteRate = b.readUInt32LE(28);
  let off = 12;
  while (off + 8 <= b.length) {
    const id = b.toString("ascii", off, off + 4), size = b.readUInt32LE(off + 4);
    if (id === "data") return size / byteRate;
    off += 8 + size + (size % 2);
  }
  throw new Error(`no data chunk in ${file}`);
}
