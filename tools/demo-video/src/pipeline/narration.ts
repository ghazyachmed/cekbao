// narration: the English script. Lines describe what the viewer should notice in the scenes that were actually
// captured. Facts (decisions, model mode, test counts) come from the capture and the evidence manifest.
// Pronunciation used for TTS: CEKBAO = "Check Bao"; NVIDIA = "en-VID-ee-uh"; Nebius = "NEB-ee-us".
import type { ScenarioCapture } from "./capture.ts";

export type Tone = "bad" | "ok" | "warn" | "info";
export type Callout = { text: string; tone: Tone };
export type NarrationLine = { id: string; scene: string; text: string; tts?: string; anchor?: string; callout?: Callout };
export type Facts = {
  inferenceMode: string;            // live | replay | mock | rules
  modelId: string | null;
  latencySeconds: number | null;
  testsPassed: number | null;
  axeViolations: number | null;
  repoUrl: string;
};

export function buildScript(captures: Record<string, ScenarioCapture>, f: Facts): NarrationLine[] {
  const live = f.inferenceMode === "live" || f.inferenceMode === "replay";
  const A = captures.conflict, B = captures.policy_change, C = captures.insufficient;
  const L = (scene: string, id: string, text: string, anchor?: string, tts?: string, callout?: Callout): NarrationLine =>
    ({ id: `${scene}_${id}`, scene, text, anchor, tts, callout });
  const info = (text: string): Callout => ({ text, tone: "info" });
  return [
    L("intro", "1", "A tuition email asks you to pay a new account."),
    L("intro", "2", "Would you pay it? CEKBAO checks before you do.", undefined,
      "Would you pay it? Check Bao checks, before you do."),
    L("intro", "3", "The name is the university's. The account belongs to someone else."),
    L("intro", "4", "Singapore police reported at least 20 school impersonation scams since March 2026.",
      undefined, "Singapore police reported at least twenty school impersonation scams since March twenty twenty-six."),
    live
      ? L("intro", "5", "CEKBAO reads it with NVIDIA Nemotron on Nebius, then checks it against the institution's policy for that date.",
          undefined, "Check Bao reads it with NVIDIA Nemotron on Nebius, then checks it against the institution's policy for that date.")
      : L("intro", "5", "CEKBAO checks it against the institution's own policy for that date.", undefined,
          "Check Bao checks it against the institution's own policy for that date."),

    L("conflict", "1", "This is the real app. We paste the email into CEKBAO.", "form_open",
      "This is the real app. We paste the email into Check Bao.", info("Paste the instruction")),
    L("conflict", "2", "It asks us to pay a new payee and a new account.", "form_filled", undefined,
      info("New payee, new account")),
    L("conflict", "3", "We choose the university from the registry.", "institution_shown", undefined,
      info("Choose the institution")),
    L("conflict", "4", "The date matters, because policies change. We plan to pay on 15 November.", "dates_shown",
      "The date matters, because policies change. We plan to pay on the fifteenth of November.",
      info("Payment date: 15 November 2026")),
    L("conflict", "5", "The check is saved first, then a worker compares it.", "submitted",
      undefined, info("Saved first, then checked")),
    L("conflict", "6", `The result: ${lower(A.headlines[0])}`, "result_shown", undefined, verdict(A.headlines[0])),
    L("conflict", "7", "Next step: do not pay these details. Contact the university.",
      "next_action_shown", undefined, info("Next: contact the university")),
    L("conflict", "8", "Payee, account and bank code conflict. Currency and method agree.",
      "explanation_shown", undefined, { text: "Payee, account, bank code conflict", tone: "bad" }),
    L("conflict", "9", "This is the policy sentence behind the result, with its version and effective date.",
      "evidence_shown", undefined, info("Policy quote, version and date")),
    L("conflict", "10", live
      ? `The instruction was read by ${f.modelId} on Nebius, in ${f.latencySeconds?.toFixed(1)} seconds.`
      : "In this preview, fixed rules read it. The NVIDIA model was not called.", "inference_shown",
      live ? `The instruction was read by NVIDIA Nemotron on Nebius, in ${f.latencySeconds?.toFixed(1)} seconds.` : undefined,
      live ? { text: f.inferenceMode === "replay" ? "Recorded NVIDIA Nemotron inference" : "Read by NVIDIA Nemotron on Nebius",
               tone: "ok" }
           : { text: "Fixed rules read it; model not called", tone: "warn" }),

    L("policy_change", "2", "Now, dates. This old invoice was paid once on 14 August. The next payment is due on 30 November.",
      "dates_shown", "Now, dates. This old invoice was paid once on the fourteenth of August. " +
      "The next payment is due on the thirtieth of November.", info("Paid 14 Aug, next due 30 Nov")),
    L("policy_change", "3", `For 30 November, the result is: ${lower(B.headlines[0])}`, "result_shown",
      `For the thirtieth of November, the result is: ${lower(B.headlines[0])}`, verdict(B.headlines[0], "30 Nov: ")),
    L("policy_change", "4", "Policy version 2026.1 took effect on 1 September, with a new account.", "explanation_shown",
      "Policy version twenty twenty-six point one took effect on the first of September, with a new account.",
      info("Policy 2026.1 since 1 September")),
    L("policy_change", "5", "The August payment matched version 2025.1.", "earlier_payment_shown",
      "The August payment matched version twenty twenty-five point one.", verdict(B.headlines[1], "14 Aug: ")),

    L("policy_timeline", "2", "Until 31 August, the old policy applied. From 1 September, a new version has a new account.",
      undefined, "Until the thirty-first of August, the old policy applied. From the first of September, a new version has a new account."),
    L("policy_timeline", "3", "One invoice, two answers. A match in the past does not approve a new payment."),

    L("insufficient", "1", "Third, a deposit request for a synthetic Canadian institute.", "submitted", undefined,
      info("Deposit request, synthetic institute")),
    L("insufficient", "2", `The result: ${lower(C.headlines[0])}`, "result_shown", undefined, verdict(C.headlines[0])),
    L("insufficient", "3", "The account matches an agent's page, but that publisher has no authority for this institution.",
      "explanation_shown", undefined, { text: "Publisher has no authority", tone: "warn" }),
    L("insufficient", "4", "The French original stays visible. The translation is labeled unofficial.", "evidence_shown",
      undefined, info("French original, unofficial translation")),


    ...(live ? [
      L("nvidia", "1", "The worker calls NVIDIA Nemotron 3 Nano on Nebius Token Factory."),
      L("nvidia", "2", "The model proposes fields with exact quotes. Code checks every quote, and fixed rules decide."),
    ] : [
      L("nvidia", "1", "The worker is built to call NVIDIA Nemotron 3 Nano on Nebius Token Factory."),
      L("nvidia", "2", "In this preview it was not called. Code checks every quote, and fixed rules decide."),
    ]),

    L("results", "1", `${f.testsPassed ?? "All"} automated tests pass, and axe found ${f.axeViolations === 0 ? "no" : f.axeViolations} accessibility violations.`),
    L("results", "2", `Limits: synthetic data, no user testing yet${live ? "" : ", and no model call in this preview"}.`),
  ];
}

/** Callout for a decision the app showed: its own headline, with the matching tone. */
function verdict(headline: string, prefix = ""): Callout {
  const tone: Tone = /^conflict/i.test(headline) ? "bad" : /^match/i.test(headline) ? "ok" : "warn";
  return { text: `${prefix}${headline.replace(/\.$/, "")}`, tone };
}

const lower = (headline: string) => headline.charAt(0).toLowerCase() + headline.slice(1);

export function narrationMarkdown(lines: NarrationLine[], audio: string): string {
  const out = ["# CEKBAO demo narration", "", `Language: English. Audio: ${audio}. Captions use the text column; ` +
    "the spoken form differs only for numbers, dates and names (CEKBAO is spoken \"Check Bao\").", ""];
  let scene = "";
  for (const l of lines) {
    if (l.scene !== scene) { scene = l.scene; out.push(`## ${scene}`, ""); }
    out.push(`- ${l.text}${l.anchor ? `  _(on screen: ${l.anchor.replace(/_/g, " ")})_` : ""}`);
    if (l.tts && l.tts !== l.text) out.push(`  - Spoken: ${l.tts}`);
  }
  return out.join("\n") + "\n";
}
