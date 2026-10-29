// captions: split narration into cues of at most two lines and export SRT.
export type Cue = { start: number; end: number; lines: string[] };
export type Line = { text: string; start: number; end: number };

export const MIN_CUE_SECONDS = 0.7;

export function wrapCaption(text: string, maxChars: number): string[] {
  const words = text.trim().split(/\s+/);
  const lines: string[] = [];
  let current = "";
  for (const w of words) {
    if (!current) current = w;
    else if ((current + " " + w).length <= maxChars) current += " " + w;
    else { lines.push(current); current = w; }
  }
  if (current) lines.push(current);
  if (lines.length === 2) {          // balance two lines so neither is a single orphan word
    const all = words.join(" ");
    let best = lines;
    let bestDiff = Infinity;
    for (let i = 1; i < words.length; i++) {
      const a = words.slice(0, i).join(" "), b = words.slice(i).join(" ");
      if (a.length <= maxChars && b.length <= maxChars && Math.abs(a.length - b.length) < bestDiff) {
        best = [a, b]; bestDiff = Math.abs(a.length - b.length);
      }
    }
    return all ? best : lines;
  }
  return lines;
}

function chunks(text: string, maxChars: number): string[] {
  // Prefer sentence boundaries, then pack words into two-line cues.
  // A sentence ends at . ! ? followed by a space or the end, so "2025.1" and "github.com" stay whole.
  const sentences = text.split(/(?<=[.!?]["')]?)\s+/).map((s) => s.trim()).filter(Boolean);
  const out: string[] = [];
  for (const s of sentences) {
    if (wrapCaption(s, maxChars).length <= 2) { out.push(s); continue; }
    out.push(...balanced(s.split(/\s+/), maxChars));
  }
  const merged: string[] = [];
  for (const part of out) {   // join very short pieces with the previous cue when both still fit in two lines
    const prev = merged.at(-1);
    if (prev && (part.length < 28 || prev.length < 28) && wrapCaption(`${prev} ${part}`, maxChars).length <= 2) {
      merged[merged.length - 1] = `${prev} ${part}`;
    } else merged.push(part);
  }
  return merged;
}

/** Fewest cues that fit in two lines each, with similar lengths (no one-word leftovers). */
function balanced(words: string[], maxChars: number): string[] {
  const total = words.join(" ").length;
  for (let n = 2; n <= words.length; n++) {
    const parts: string[] = [];
    let cur: string[] = [];
    for (const [i, w] of words.entries()) {
      const left = n - parts.length;       // parts still to fill, including the current one
      const remaining = words.length - i;
      if (cur.length && left > 1 && ([...cur, w].join(" ").length > total / n || remaining < left)) {
        parts.push(cur.join(" ")); cur = [];
      }
      cur.push(w);
    }
    parts.push(cur.join(" "));
    if (parts.every((p) => wrapCaption(p, maxChars).length <= 2)) return parts;
  }
  return words;
}

export function splitIntoCues(line: Line, maxChars: number): Cue[] {
  const parts = chunks(line.text, maxChars);
  const total = parts.reduce((n, p) => n + p.length, 0);
  const span = line.end - line.start;
  // Every cue gets the minimum reading time first; the rest is shared by length.
  const floor = Math.min(MIN_CUE_SECONDS, span / parts.length);
  const spare = Math.max(0, span - floor * parts.length);
  const cues: Cue[] = [];
  let t = line.start;
  parts.forEach((p, i) => {
    const end = i === parts.length - 1 ? line.end : t + floor + spare * (p.length / total);
    cues.push({ start: round(t), end: round(end), lines: wrapCaption(p, maxChars) });
    t = end;
  });
  return cues;
}

const round = (x: number) => Math.round(x * 1000) / 1000;

export function validateCues(cues: Cue[], maxChars: number): string[] {
  const errors: string[] = [];
  cues.forEach((c, i) => {
    if (c.lines.length > 2) errors.push(`cue ${i + 1} has ${c.lines.length} lines`);
    for (const l of c.lines) if (l.length > maxChars) errors.push(`cue ${i + 1} line longer than ${maxChars} chars`);
    if (c.end - c.start < MIN_CUE_SECONDS) errors.push(`cue ${i + 1} too short (${(c.end - c.start).toFixed(2)} s)`);
    if (i > 0 && c.start < cues[i - 1].end - 1e-6) errors.push(`cue ${i + 1} overlaps cue ${i}`);
  });
  return errors;
}

function stamp(s: number): string {
  const ms = Math.round(s * 1000);
  const h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, sec = Math.floor(ms / 1000) % 60;
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${pad(h)}:${pad(m)}:${pad(sec)},${pad(ms % 1000, 3)}`;
}

export function toSrt(cues: Cue[]): string {
  return cues.map((c, i) => `${i + 1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${c.lines.join("\n")}\n`).join("\n");
}
