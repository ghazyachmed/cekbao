// YouTube package logic: chapters from the final timeline, limit checks and claim checks.
// Limits verified 2026-10-28 on YouTube Help: title 100 characters, description 5,000 characters, no angle
// brackets; chapters start at 00:00, at least three in ascending order, each at least 10 seconds.
export type Chapter = { start: number; title: string };
type SceneLike = { id: string; from: number; durationInFrames: number };

// External sources quoted in the video or the description, each opened and checked on the date given.
export const VERIFIED_SOURCES = {
  policeAdvisory: {
    url: "https://www.police.gov.sg/media-hub/news/2026/03/20260319_police_advisory_on_resurgence_of_impersonation_scams_involving_educational_institutions",
    checked_on: "2026-10-28",
    supports: "Singapore Police Force, 19 March 2026: at least 20 cases since March 2026, losses of at least S$31,000; " +
              "emails asked for urgent payment of school or tuition fees to a bank account",
  },
};

export const TITLE_MAX = 100;
export const DESCRIPTION_MAX = 5000;
const MIN_CHAPTER = 10;

const GROUPS: [string[], (mode: string) => string][] = [
  [["intro"], () => "The problem: a payment email with a new account"],
  [["title_conflict", "conflict"], () => "A conflicting payment instruction"],
  [["title_policy_change", "policy_change", "policy_timeline"], () => "Policy versions and payment dates"],
  [["title_insufficient", "insufficient", "escalation"], () => "Insufficient evidence: a publisher without authority"],
  [["nvidia"], (m) => (m === "live" || m === "replay" ? "NVIDIA Nemotron on Nebius" : "Model integration status")],
  [["results"], () => "Results and limits"],
];

export function buildChapters(scenes: SceneLike[], fps: number, durationSeconds: number, mode: string): Chapter[] {
  const chapters: Chapter[] = [];
  for (const [ids, title] of GROUPS) {
    const first = scenes.find((s) => ids.includes(s.id));
    if (first) chapters.push({ start: Math.floor(first.from / fps), title: title(mode) });
  }
  if (chapters.length) chapters[0].start = 0;
  // Merge any chapter shorter than the minimum into its predecessor (the first one into its successor).
  let changed = true;
  while (changed && chapters.length > 1) {
    changed = false;
    for (let i = 0; i < chapters.length; i++) {
      const end = i + 1 < chapters.length ? chapters[i + 1].start : durationSeconds;
      if (end - chapters[i].start < MIN_CHAPTER) {
        if (i === 0) chapters.splice(1, 1);
        else {
          const merged = `${chapters[i - 1].title} and ${chapters[i].title.charAt(0).toLowerCase()}${chapters[i].title.slice(1)}`;
          chapters[i - 1].title = merged.length <= 60 ? merged : chapters[i - 1].title;
          chapters.splice(i, 1);
        }
        changed = true;
        break;
      }
    }
  }
  return chapters;
}

export function validateChapters(ch: Chapter[], durationSeconds: number): string[] {
  const errors: string[] = [];
  if (!ch.length || ch[0].start !== 0) errors.push("the first chapter must start at 00:00");
  if (ch.length < 3) errors.push("YouTube needs at least three chapters");
  ch.forEach((c, i) => {
    const end = i + 1 < ch.length ? ch[i + 1].start : durationSeconds;
    if (i > 0 && c.start <= ch[i - 1].start) errors.push(`chapter ${i + 1} does not start after chapter ${i}`);
    if (end - c.start < MIN_CHAPTER) errors.push(`chapter ${i + 1} ("${c.title}") is shorter than 10 seconds`);
    if (c.start >= durationSeconds) errors.push(`chapter ${i + 1} starts after the video ends`);
  });
  return errors;
}

export const mmss = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export function chapterText(ch: Chapter[]): string {
  return ch.map((c) => `${mmss(c.start)} ${c.title}`).join("\n");
}

export function checkLengths(title: string, description: string): string[] {
  const errors: string[] = [];
  if (title.length > TITLE_MAX) errors.push(`title has ${title.length} characters (limit 100)`);
  if (description.length > DESCRIPTION_MAX) errors.push(`description has ${description.length} characters (limit 5000)`);
  if (/[<>]/.test(title + description)) errors.push("angle brackets are not allowed in titles or descriptions");
  return errors;
}

const UNSUPPORTED: [RegExp, string][] = [
  [/safe to pay|payment is safe|guarantee/i, "safety or guarantee claim"],
  [/scam detected|fraud (?:prevented|stopped|blocked)|prevents? fraud|reduces? fraud/i, "fraud-outcome claim"],
  [/\d+(?:\.\d+)?\s?%/, "percentage figure without a source"],
  [/trusted by|(?<!\bnot )\b(?:our )?customers?\b|used by|partners? with/i, "customer or endorsement claim"],
  [/world'?s first|first[- ]ever|revolutionary|novel|unique approach/i, "novelty claim"],
];
const LIVE_ONLY = /live (?:call|inference|NVIDIA)|real[- ]time (?:NVIDIA|inference)|powered by NVIDIA|NVIDIA[- ]powered/i;

export function checkClaims(text: string, mode: string): string[] {
  const errors = UNSUPPORTED.filter(([rx]) => rx.test(text)).map(([, what]) => `unsupported ${what}`);
  const live = mode === "live" || mode === "replay";
  if (!live && LIVE_ONLY.test(text)) errors.push("mentions live NVIDIA inference, but the recording did not call the model");
  return errors;
}
