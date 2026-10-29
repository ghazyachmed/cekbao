// Visual identity shared with the app (policyguard/web/static/tokens.css): Inter, navy canvas, teal action accent.
export const C = {
  canvas: "#0b1b2b",
  panel: "#112335",
  line: "#2a4a66",
  text: "#ffffff",
  muted: "#b9c7d3",        // 9.9:1 on canvas
  teal: "#3fdcc0",         // 10.6:1 on canvas
  bad: "#ff8a94",
  warn: "#f5c862",
  synthetic: "#f5c862",
  cardInk: "#0b1b2b",
  card: "#ffffff",
};
// Video palette: brighter accents on a deep navy stage. Every accent passes 4.5:1 against V.bg as text,
// and V.ink passes 4.5:1 on every accent as a fill (tone pills use dark ink on a bright fill).
export const V = {
  bg: "#060b18",
  panel: "#0f1a31",
  ink: "#060b18",
  teal: "#2ee6c5",
  coral: "#ff6b7d",
  amber: "#ffc53d",
  violet: "#a08cff",
  blue: "#4fb0ff",
  pink: "#ff7ad9",
  green: "#76b900",       // NVIDIA green, used only for the NVIDIA model step
};
export type Tone = "bad" | "ok" | "warn" | "info";
export const TONE: Record<Tone, { color: string; glyph: string }> = {
  bad: { color: V.coral, glyph: "✕" }, ok: { color: V.teal, glyph: "✓" },
  warn: { color: V.amber, glyph: "!" }, info: { color: V.blue, glyph: "→" },
};
// Two accents per scene: the backdrop glows and the frame border.
export const ACCENT: Record<string, [string, string]> = {
  intro: [V.coral, V.violet], title_conflict: [V.coral, V.pink], conflict: [V.coral, V.blue],
  title_policy_change: [V.violet, V.blue], policy_change: [V.violet, V.teal], policy_timeline: [V.violet, V.teal],
  title_insufficient: [V.amber, V.coral], insufficient: [V.amber, V.blue], escalation: [V.blue, V.teal],
  nvidia: [V.green, V.teal], results: [V.teal, V.violet],
};
export const FONT = "Inter, system-ui, sans-serif";
// 1920x1080 frame with ~5% safe margins (96 px sides, 54 px top and bottom). Captions sit below the app frame.
export const L = { safeX: 96, safeY: 54, headerTop: 54, frameX: 272, frameY: 112, frameW: 1376, frameH: 774,
                   captionTop: 898, captionBottom: 1026 };
