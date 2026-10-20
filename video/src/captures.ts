// Typed access to the real capture manifest written by capture/capture.mjs.
import manifest from "../public/captures/manifest.json";

export type Box = { x: number; y: number; w: number; h: number };
type ShotMeta = {
  name: string; file: string; note: string; fullPage?: boolean; pxHeight?: number;
  click?: (Box & { persona?: Box | null }) | null; boxes?: Record<string, Box[]>;
};
type ApiMeta = { label: string; method: string; path: string; status: number; body: string };

const shots = manifest.shots as unknown as ShotMeta[];
export const API = manifest.api as unknown as ApiMeta[];
export const CAPTURED_AT = manifest.capturedAtUtc as string;
export const CAPTURE_COMMIT = (manifest as unknown as { gitCommit: string }).gitCommit;

export const meta = (name: string): ShotMeta => {
  const s = shots.find((x) => x.name === name);
  if (!s) throw new Error(`capture ${name} missing from manifest`);
  return s;
};

export const imgSize = (name: string) => {
  const m = meta(name);
  return { w: 1920, h: m.fullPage ? (m.pxHeight as number) : 1080 };
};

export const box = (name: string, key: string, i = 0): Box => {
  const b = meta(name).boxes?.[key]?.[i];
  if (!b) throw new Error(`box ${key}[${i}] missing in ${name}`);
  return b;
};

export const clickBox = (name: string, which: "button" | "persona" = "button"): Box => {
  const c = meta(name).click;
  if (!c) throw new Error(`no click target in ${name}`);
  if (which === "persona") {
    if (!c.persona) throw new Error(`no persona target in ${name}`);
    return c.persona;
  }
  return { x: c.x, y: c.y, w: c.w, h: c.h };
};

export const center = (b: Box) => ({ x: b.x + b.w / 2, y: b.y + b.h / 2 });

export const apiResult = (labelStart: string) => {
  const a = API.find((x) => x.label.startsWith(labelStart));
  if (!a) throw new Error(`api result ${labelStart} missing`);
  return a;
};
