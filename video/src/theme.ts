// Visual system and scene timing for the CEKBAO demo video.
// Times are in seconds; components convert with fps from useVideoConfig().

export const C = {
  bg: "#070B10",
  panel: "#0D141C",
  line: "#EAF2F5",
  dim: "#8FA3B0",
  faint: "#2A3742",
  teal: "#22B5B2", // matched / approved
  coral: "#F27468", // conflict
  gold: "#F6CA70", // missing evidence / unconfirmed
};

export const FONT = "Lato, Arial, sans-serif";
export const MONO = "Menlo, 'SF Mono', Consolas, monospace";

export const W = 1920;
export const H = 1080;
export const MARGIN_X = 120;
export const MARGIN_Y = 100;

// Real-capture layout: browser bar + app viewport above the caption band.
export const VIEW_TOP = 64;
export const VIEW_BOTTOM = 846;

export const COMMIT = "f33a98d";
export const COMMIT_NOTE = "app code identical to 715ea9c";
export const REPO_URL = "github.com/Ghazyachmed/cekbao";

export type SceneId =
  | "hook" | "mechanism" | "evidence" | "root" | "reveal"
  | "demoA" | "demoB" | "demoC" | "security" | "tests" | "close";

export const SCENES: { id: SceneId; start: number; end: number; title: string; kind: "illustrative" | "capture" | "evidence" }[] = [
  { id: "hook", start: 0, end: 12, title: "Hook", kind: "illustrative" },
  { id: "mechanism", start: 12, end: 30, title: "Mechanism", kind: "illustrative" },
  { id: "evidence", start: 30, end: 47, title: "Reported evidence", kind: "evidence" },
  { id: "root", start: 47, end: 63, title: "Root cause", kind: "illustrative" },
  { id: "reveal", start: 63, end: 76, title: "CEKBAO", kind: "illustrative" },
  { id: "demoA", start: 76, end: 120, title: "Scenario A", kind: "capture" },
  { id: "demoB", start: 120, end: 162, title: "Scenario B", kind: "capture" },
  { id: "demoC", start: 162, end: 204, title: "Scenario C", kind: "capture" },
  { id: "security", start: 204, end: 226, title: "Security", kind: "capture" },
  { id: "tests", start: 226, end: 244, title: "Evidence and limits", kind: "evidence" },
  { id: "close", start: 244, end: 253, title: "Close", kind: "illustrative" },
];

export const TOTAL_SECONDS = 253;
