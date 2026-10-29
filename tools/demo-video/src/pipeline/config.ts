// configuration: load and validate demo.config.json.
import fs from "node:fs";

export type VideoConfig = {
  width: number; height: number; fps: number; duration_target_seconds: number;
  duration_limit_seconds: number | null; language: string; subtitles: string; output: string;
};
export type CaptureConfig = {
  base_url: string; port: number; data: "synthetic"; inference: "live" | "replay" | "mock";
  max_paid_calls: number; max_cost_usd: number | null;
};
export type DemoConfig = { video: VideoConfig; capture: CaptureConfig; tts?: { engine: string; voice: string; speed: number };
  music?: { enabled: boolean }; rules_source?: { url: string; checked_on: string; video_rule: string };
  // Why the model could not be called, shown in previews only (short: video card; long: YouTube description).
  inference_blocker?: { short: string; long: string } };

const HARD_PAID_CALL_CAP = 3;

export function validateConfig(raw: any): { config?: DemoConfig; errors: string[] } {
  const errors: string[] = [];
  const v = raw?.video ?? {};
  const c = raw?.capture ?? {};
  for (const k of ["width", "height", "fps", "duration_target_seconds"]) {
    if (!Number.isInteger(v[k]) || v[k] <= 0) errors.push(`video.${k} must be a positive integer`);
  }
  if (![24, 25, 30, 60].includes(v.fps)) errors.push("video.fps must be 24, 25, 30 or 60");
  if (v.duration_limit_seconds !== null && v.duration_limit_seconds !== undefined) {
    if (!(v.duration_limit_seconds > 0)) errors.push("video.duration_limit_seconds must be positive or null");
    else if (v.duration_target_seconds > v.duration_limit_seconds) {
      errors.push("video.duration_target_seconds exceeds the official duration limit");
    }
  }
  if (v.language !== "en" || v.subtitles !== "en") errors.push("video.language and video.subtitles must be en");
  if (typeof v.output !== "string" || !v.output.endsWith(".mp4")) errors.push("video.output must end with .mp4");
  if (c.data !== "synthetic") errors.push("capture.data must be synthetic; real user data is never recorded");
  if (!["live", "replay", "mock"].includes(c.inference)) errors.push("capture.inference must be live, replay or mock");
  if (!Number.isInteger(c.max_paid_calls) || c.max_paid_calls < 0 || c.max_paid_calls > HARD_PAID_CALL_CAP) {
    errors.push(`capture.max_paid_calls must be between 0 and ${HARD_PAID_CALL_CAP}`);
  }
  if (!Number.isInteger(c.port) || c.port < 1024) errors.push("capture.port must be an integer >= 1024");
  return errors.length ? { errors } : { config: raw as DemoConfig, errors };
}

export function loadConfig(path: string): DemoConfig {
  const { config, errors } = validateConfig(JSON.parse(fs.readFileSync(path, "utf8")));
  if (!config) throw new Error(`Invalid ${path}:\n- ${errors.join("\n- ")}`);
  return config;
}

export function resolveBaseUrl(cfg: CaptureConfig): string | null {
  if (cfg.base_url.startsWith("env:")) return process.env[cfg.base_url.slice(4)] || null;
  return cfg.base_url;
}
