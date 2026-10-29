// browser_capture: record the real CEKBAO app with Playwright (discover -> rehearse -> record).
// Sync waits use app state; editorial pauses (hold) only give viewers time to read. The page is never modified:
// click positions are recorded as markers and drawn later by the composition.
import { chromium, type Browser, type Locator, type Page } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { assertCaptureComplete, type Marker } from "./capture-markers.ts";
import type { Scenario } from "./scenarios.ts";

export const VIEW = { width: 1440, height: 810 };
const MOBILE = { width: 390, height: 844 };   // final 16:9 aspect; app content fills most of the frame
export type Still = { name: string; file: string; width: number; height: number };
export type ScenarioCapture = {
  key: string; code: string; title: string; video: string; final_still: string; markers: Marker[];
  case_path: string; headlines: string[]; inference_text: string; stills: Still[]; evidence_titles: string[];
  status_seen: string; viewport: { width: number; height: number };
};
// Sandbox test values from policyguard/fixtures/demo_users.json. Access codes go into password inputs (masked).
export const USERS = { payer: { id: "pg_payer", code: "demo-payer-2026" },
                       reviewer: { id: "pg_reviewer", code: "demo-reviewer-2026" } };

type Ctx = { page: Page; mark: (label: string, detail?: string, at?: { x: number; y: number }) => void;
             hold: (ms: number) => Promise<void>; record: boolean };

async function click(c: Ctx, loc: Locator, label: string): Promise<void> {
  await loc.waitFor();
  const box = await loc.boundingBox();
  if (!box) throw new Error(`no box for ${label}`);
  c.mark(`click:${label}`, undefined, { x: Math.round(box.x + box.width / 2), y: Math.round(box.y + box.height / 2) });
  await c.hold(450);                       // let the drawn cursor arrive before the click
  await loc.click();
}

async function signIn(c: Ctx, user: { id: string; code: string }, typed: boolean): Promise<void> {
  const { page } = c;
  await page.goto("/check/sign-in");
  await page.getByLabel("User ID").waitFor();
  c.mark("sign_in_page");
  if (typed) {
    await page.getByLabel("User ID").pressSequentially(user.id, { delay: 35 });
    await page.getByLabel("Access code").pressSequentially(user.code, { delay: 25 });
  } else {
    await page.getByLabel("User ID").fill(user.id);
    await page.getByLabel("Access code").fill(user.code);
  }
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/(check|review)/);
}

async function checkFlow(c: Ctx, s: Scenario): Promise<{ inference: string; status: string }> {
  const { page } = c;
  await signIn(c, USERS.payer, false);
  await page.getByRole("heading", { name: "Check payment instructions" }).waitFor();
  c.mark("form_open");
  await c.hold(1200);
  await page.locator("#example").selectOption(s.key);
  await click(c, page.getByRole("button", { name: "Use example" }), "use_example");
  await page.waitForURL(new RegExp(`example=${s.key}`));
  await page.locator("#instruction_text").waitFor();
  c.mark("form_filled");
  await smoothScrollTo(page, page.locator("#instruction_text"));
  await c.hold(4000);
  if (s.steps.includes("institution")) {
    await smoothScrollTo(page, page.locator("#institution_choice"));
    c.mark("institution_shown");
    await c.hold(3000);
  }
  if (s.key === "policy_change") {        // the earlier payment date sits in a disclosure (open when filled)
    const disclosure = page.locator("details:has(#paid_on)");
    if (!(await disclosure.evaluate((d) => (d as HTMLDetailsElement).open))) {
      await click(c, page.getByText("I already paid using these details"), "paid_before");
    }
  }
  await smoothScrollTo(page, page.locator("#due_on"));
  c.mark("dates_shown");
  await c.hold(s.key === "policy_change" ? 5000 : 3000);
  const submit = page.getByRole("button", { name: "Check instructions" });
  await smoothScrollTo(page, submit);
  await click(c, submit, "check_instructions");
  c.mark("submitted");
  await page.waitForURL(/\/check\/cases\//);
  const status = await page.locator("#status-label, h1.decision-label").first().innerText();
  c.mark("status_shown", status);
  const headline = page.locator("h1.decision-label");
  await headline.waitFor({ timeout: 90000 });
  c.mark("result_shown", await headline.innerText());
  await c.hold(3000);
  if (s.steps.includes("next_action")) {
    await smoothScrollTo(page, page.locator("#next-action"));
    c.mark("next_action_shown");
    await c.hold(3500);
  }
  await smoothScrollTo(page, page.locator("#explanation"));
  c.mark("explanation_shown");
  await c.hold(5000);
  await smoothScrollTo(page, page.locator("#evidence"));
  c.mark("evidence_shown");
  await c.hold(5000);
  if (s.steps.includes("earlier_payment")) {
    await smoothScrollTo(page, page.locator(".secondary-assessment"));
    c.mark("earlier_payment_shown");
    await c.hold(5500);
  }
  let inference = "";
  if (s.steps.includes("inference")) {
    const summary = page.getByText("What we read from the instruction");
    await smoothScrollTo(page, summary);
    await click(c, summary, "read_details");
    inference = await readFrom(page);
    c.mark("inference_shown", inference);
    await c.hold(4500);
  }
  return { inference, status };
}

async function reviewFlow(c: Ctx, caseRef: string, snap?: (name: string, url: string, selectors: string[]) => Promise<void>)
  : Promise<{ inference: string; status: string }> {
  const { page } = c;
  await signIn(c, USERS.reviewer, false);
  await page.goto("/review");
  await page.getByRole("heading", { name: "Review queue" }).waitFor();
  const row = page.locator(`tr:has(a[href="/review/cases/${caseRef}"])`);
  await row.waitFor();
  c.mark("queue_shown");
  // Zoom crop of this exact moment (the case still awaits review), taken in a separate unrecorded 2x page.
  if (c.record && snap) await snap("queue_shown", "/review", ["table.table thead", `tr:has(a[href="/review/cases/${caseRef}"])`]);
  await c.hold(3500);
  await click(c, row.getByRole("link", { name: /Open/ }), "open_case");
  await page.waitForURL(new RegExp(`/review/cases/${caseRef}`));
  await page.locator("h1.decision-label").waitFor();
  c.mark("review_case_shown");
  await c.hold(2500);
  const form = page.getByRole("heading", { name: "Record a review" });
  await smoothScrollTo(page, form);
  await page.getByLabel("More information is needed").check();
  await page.getByLabel("Reason").pressSequentially("Asked the Kestrel Ridge bursar to confirm the deposit account.",
                                                    { delay: 22 });
  c.mark("review_filled");
  await c.hold(1500);
  await click(c, page.getByRole("button", { name: "Record review" }), "record_review");
  await page.getByText("Review recorded.").waitFor();
  c.mark("review_recorded");
  await c.hold(1500);
  await smoothScrollTo(page, page.getByRole("heading", { name: "Review history" }));
  c.mark("review_history_shown");
  await c.hold(3500);
  return { inference: "", status: "" };
}

export async function captureScenario(browser: Browser, baseUrl: string, s: Scenario, outDir: string,
                                      opts: { record: boolean; caseRef?: string }): Promise<ScenarioCapture> {
  const ctx = await browser.newContext({ baseURL: baseUrl, viewport: VIEW, deviceScaleFactor: 1, colorScheme: "light",
    reducedMotion: "reduce", ...(opts.record ? { recordVideo: { dir: path.join(outDir, "tmp-video"), size: VIEW } } : {}) });
  const page = await ctx.newPage();
  const t0 = Date.now();
  const markers: Marker[] = [];
  const c: Ctx = { page, record: opts.record,
    mark: (label, detail, at) => markers.push({ label, t: (Date.now() - t0) / 1000, detail, ...(at ? { at } : {}) }),
    hold: (ms) => (opts.record ? page.waitForTimeout(ms) : Promise.resolve()) };
  try {
    const early: Still[] = [];
    const snap = async (name: string, url: string, selectors: string[]) => {
      const sctx = await browser.newContext({ baseURL: baseUrl, viewport: VIEW, deviceScaleFactor: 2,
                                              storageState: await ctx.storageState(), colorScheme: "light", reducedMotion: "reduce" });
      const spage = await sctx.newPage();
      await spage.goto(url);
      early.push(await clipStill(spage, selectors, path.join(outDir, `${s.key}-${name}.png`), name));
      await sctx.close();
    };
    const out = s.key === "escalation" ? await reviewFlow(c, opts.caseRef!, snap) : await checkFlow(c, s);
    c.mark("end");
    if (!opts.record) {
      const rehearsedCase = new URL(page.url()).pathname;
      await ctx.close();
      assertCaptureComplete(s.key, markers, s.required);
      return { case_path: rehearsedCase } as ScenarioCapture;   // rehearsal: every selector and assertion passed
    }
    const finalStill = path.join(outDir, `${s.key}-final.png`);
    await page.screenshot({ path: finalStill });
    const casePath = new URL(page.url()).pathname;
    const headlines = await page.locator(".decision-label").allInnerTexts();
    const evidenceTitles = await page.locator(".evidence h3").allInnerTexts();
    const state = await ctx.storageState();
    const video = page.video();
    await ctx.close();                     // finalize the recording before using it
    const videoFile = path.join(outDir, `${s.key}.webm`);
    await video!.saveAs(videoFile);
    await video!.delete();
    const stills = await zoomStills(browser, baseUrl, casePath, state, outDir, s);
    stills.list.unshift(...early);
    assertCaptureComplete(s.key, markers, s.required);
    if (s.key !== "escalation") {
      for (const [i, expected] of s.expected.entries()) {
        if (headlines[i] !== expected) throw new Error(`scenario ${s.key}: expected "${expected}", app showed "${headlines[i]}"`);
      }
    }
    return { key: s.key, code: s.code, title: s.title, video: path.basename(videoFile),
      final_still: path.basename(finalStill), markers, case_path: casePath, headlines,
      inference_text: out.inference || stills.inference, stills: stills.list, evidence_titles: evidenceTitles,
      status_seen: out.status, viewport: VIEW };
  } catch (e) {
    await ctx.close().catch(() => undefined);
    throw new Error(`${opts.record ? "recording" : "rehearsal"} of scenario ${s.key} failed: ${(e as Error).message}`);
  }
}

async function readFrom(page: Page): Promise<string> {
  const line = await page.locator("details.disclosure[open] p.hint").first().innerText();
  return line.replace(/^How the instruction was read:\s*/, "").replace(/\.$/, "");
}

// Zoom targets: the exact element under discussion (union of selectors), not the whole screen.
const ZOOMS: Record<string, [string, string[]][]> = {
  conflict: [["form_filled", ["#instruction_text"]], ["result_shown", [".result > .decision"]],
    ["next_action_shown", ["#next-action .next-text", "#next-action .contact-row"]],
    ["explanation_shown", [".compare-table thead", ".compare-table tbody tr:nth-child(3)"]],
    ["evidence_shown", ["#evidence .evidence .quote"]], ["inference_shown", ["details.disclosure[open] p.hint"]],
    ["thumb_decision", [".result > .decision .icon", ".result > .decision .decision-context", ".result > .decision .decision-label"]]],
  policy_change: [["dates_shown", ["fieldset .field:has(> #due_on)", ".field:has(> #paid_on)"]], ["result_shown", [".result > .decision"]],
    ["explanation_shown", [".compare-table thead", ".compare-table tbody tr:nth-child(2)"]],
    ["earlier_payment_shown", [".secondary-assessment .decision", ".secondary-assessment .evidence .facts > div:nth-child(2)"]],
    ["thumb_decision", [".result > .decision .icon", ".result > .decision .decision-context", ".result > .decision .decision-label"]],
    ["thumb_earlier", [".secondary-assessment .decision .icon", ".secondary-assessment .decision .decision-context",
                       ".secondary-assessment .decision .decision-label"]]],
  insufficient: [["result_shown", [".result > .decision"]],
    ["explanation_shown", [".compare-table thead", ".compare-table tbody tr:nth-child(2)"]],
    ["evidence_shown", ["#evidence .evidence .quote", "#evidence .evidence .translation"]],
    ["thumb_decision", [".result > .decision .icon", ".result > .decision .decision-context", ".result > .decision .decision-label"]]],
  escalation: [["review_history_shown", ["section[aria-labelledby=\"review-history\"] ol.timeline"]]],
};

async function zoomStills(browser: Browser, baseUrl: string, casePath: string, state: any, outDir: string,
                          s: Scenario): Promise<{ list: Still[]; inference: string }> {
  const ctx = await browser.newContext({ baseURL: baseUrl, viewport: VIEW, deviceScaleFactor: 2, storageState: state,
                                         colorScheme: "light", reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const list: Still[] = [];
  let inference = "";
  for (const [anchor, selectors] of ZOOMS[s.key] ?? []) {
    const target = anchor === "form_filled" || anchor === "dates_shown" ? `/check?example=${s.key}` : casePath;
    if (page.url() !== new URL(target, baseUrl).href) await page.goto(target);
    if (anchor === "inference_shown") {
      await page.getByText("What we read from the instruction").click();
      inference = await readFrom(page);
    }
    list.push(await clipStill(page, selectors, path.join(outDir, `${s.key}-${anchor}.png`), anchor));
  }
  await ctx.close();
  if (s.key !== "escalation") list.push(await mobileStill(browser, baseUrl, casePath, state, outDir, s.key));
  fs.writeFileSync(path.join(outDir, `${s.key}-stills.json`), JSON.stringify(list, null, 2));
  return { list, inference };
}

/** First screen of the result page on a phone (390x844 CSS px at 3x), for thumbnails in a phone frame. */
async function mobileStill(browser: Browser, baseUrl: string, casePath: string, state: any, outDir: string,
                           key: string): Promise<Still> {
  const ctx = await browser.newContext({ baseURL: baseUrl, viewport: MOBILE, deviceScaleFactor: 3, storageState: state,
                                         colorScheme: "light", reducedMotion: "reduce", isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  await page.goto(casePath);
  await page.locator(".result > .decision").first().waitFor();
  const file = path.join(outDir, `${key}-mobile.png`);
  await page.screenshot({ path: file });
  await ctx.close();
  return { name: "mobile", file: path.basename(file), width: MOBILE.width, height: MOBILE.height };
}

/** Full-page crop around the union of the selectors (document coordinates, independent of scrolling). */
async function clipStill(page: Page, selectors: string[], file: string, name: string): Promise<Still> {
  const boxes = [];
  for (const sel of selectors) {
    const loc = page.locator(sel).first();
    await loc.waitFor();
    boxes.push(await loc.evaluate((el) => {
      const r = el.getBoundingClientRect();
      return { x: r.left + window.scrollX, y: r.top + window.scrollY, r: r.right + window.scrollX, b: r.bottom + window.scrollY };
    }));
  }
  const pad = 12;
  const x = Math.max(0, Math.min(...boxes.map((a) => a.x)) - pad), y = Math.max(0, Math.min(...boxes.map((a) => a.y)) - pad);
  const width = Math.max(...boxes.map((a) => a.r)) + pad - x, height = Math.max(...boxes.map((a) => a.b)) + pad - y;
  await page.screenshot({ path: file, fullPage: true, clip: { x, y, width, height } });
  return { name, file: path.basename(file), width: Math.round(width), height: Math.round(height) };
}

/** Scroll in small steps so viewers can follow; stops with the element near the top. */
async function smoothScrollTo(page: Page, loc: Locator): Promise<void> {
  await loc.waitFor();
  const target = await loc.evaluate((el) => el.getBoundingClientRect().top + window.scrollY - 110);
  const start = await page.evaluate(() => window.scrollY);
  const max = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);
  const end = Math.max(0, Math.min(target, max));
  for (let i = 1; i <= 14; i++) {
    await page.evaluate((v) => window.scrollTo(0, v), start + ((end - start) * i) / 14);
    await page.waitForTimeout(28);
  }
}

export async function launch(channel = process.env.PW_CHANNEL || "chrome"): Promise<Browser> {
  return chromium.launch({ channel });
}
