// Real CEKBAO capture. Drives the running sandbox app (http://127.0.0.1:8765) with
// Playwright and the locally installed Google Chrome. Saves full-resolution
// screenshots, real click target boxes and real HTTP responses to
// public/captures/. Nothing here is mocked: every image is the live app.
//
// Start the app first (from the repository root):
//   CEKBAO_DB_PATH=data/video_demo.sqlite3 .venv/bin/python -m uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8765
// Then:  npm run capture
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";

const BASE = process.env.CEKBAO_URL || "http://127.0.0.1:8765";
const OUT = new URL("../public/captures/", import.meta.url).pathname;
const VIEW = { width: 1600, height: 900 };
const DSF = 1.2; // 1600x900 CSS px -> 1920x1080 image px
const CODES = { stu_ayu: "demo-ayu-2026", stu_budi: "demo-budi-2026", stu_citra: "demo-citra-2026", officer_nbu: "demo-officer-2026" };
mkdirSync(OUT, { recursive: true });

const manifest = { capturedAtUtc: new Date().toISOString(), baseUrl: BASE, viewportCss: VIEW, deviceScaleFactor: DSF, shots: [], api: [] };
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

async function shot(page, name, note, click) {
  await pause(350);
  const file = `${name}.png`;
  await page.screenshot({ path: OUT + file });
  manifest.shots.push({ name, file, note, click: click || null, scrollY: await page.evaluate(() => window.scrollY) });
  console.log("shot", name, "-", note);
}
// Element boxes in full-page image pixels, so the video can pan to exact UI regions.
const BOX_TARGETS = [
  ["verdict", ".verdict"], ["contact", ".contact"], ["locked", ".locked"], ["plan", ".plan"],
  ["quoteGrid", ".quote-grid"], ["resultGrid", ".result-grid"], ["slipCards", ".slip-card"], ["checkRows", "details.check"],
  ["panelNext", "h3:What to do now"], ["panelChecks", "h3:What we checked"], ["panelWarnings", "h3:Warning signs"],
  ["panelCosts", "h3:Compare transfer costs"], ["panelPlan", "h3:Sandbox payment plan"], ["panelSlips", "h3:Each slip"],
  ["tech", "details.tech"], ["slipForm", "#slip-rows"], ["requestForm", "#tab-request .panel"],
];
async function full(page, name, note) {
  await pause(300);
  const file = `${name}.png`;
  await page.screenshot({ path: OUT + file, fullPage: true });
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  const boxes = await page.evaluate(([targets, dsf]) => {
    const out = {};
    const rect = (el) => { const r = el.getBoundingClientRect(); return { x: Math.round(r.left * dsf), y: Math.round((r.top + window.scrollY) * dsf), w: Math.round(r.width * dsf), h: Math.round(r.height * dsf) }; };
    for (const [key, sel] of targets) {
      let els = [];
      if (sel.startsWith("h3:")) {
        const h3 = [...document.querySelectorAll(".tabpane:not(.hidden) h3, .tabpane:not(.hidden) h2")].find((x) => x.textContent.trim().startsWith(sel.slice(3)));
        if (h3) els = [h3.closest("section.panel, .panel") || h3];
      } else {
        els = [...document.querySelectorAll(sel)].filter((e) => e.offsetParent !== null);
      }
      if (els.length) out[key] = els.map(rect);
    }
    return out;
  }, [BOX_TARGETS, DSF]);
  manifest.shots.push({ name, file, note, fullPage: true, cssHeight: h, pxHeight: Math.round(h * DSF), boxes });
  console.log("full", name, h, Object.keys(boxes).join(","));
}
async function box(locator) {
  const b = await locator.boundingBox();
  return b ? { x: Math.round(b.x * DSF), y: Math.round(b.y * DSF), w: Math.round(b.width * DSF), h: Math.round(b.height * DSF) } : null;
}
async function scrollTo(page, selector, offset = 24) {
  await page.evaluate(([sel, off]) => {
    const el = document.querySelector(sel);
    window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - off, behavior: "instant" });
  }, [selector, offset]);
  await pause(250);
}
async function scrollToText(page, text, offset = 24) {
  await page.evaluate(([t, off]) => {
    const el = [...document.querySelectorAll("h2,h3")].find((h) => h.textContent.trim().startsWith(t));
    window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - off, behavior: "instant" });
  }, [text, offset]);
  await pause(250);
}
async function signIn(page, user, label, prefix) {
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.evaluate(() => window.scrollTo(0, 0));
  const persona = page.getByRole("radio", { name: new RegExp(label) });
  const pbox = await box(persona);
  await persona.click();
  await page.locator("#login-code").fill(CODES[user]);
  const btn = page.locator("#login-btn");
  await shot(page, `${prefix}_signin`, `Sign-in page, persona ${label} selected, sandbox access code typed (masked)`, { ...(await box(btn)), persona: pbox });
  await btn.click();
  await page.locator("#app-view:not(.hidden)").waitFor();
}
async function signOut(page) {
  await page.locator("#logout").click();
  await page.locator("#login-view:not(.hidden)").waitFor();
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
const ctx = await browser.newContext({ viewport: VIEW, deviceScaleFactor: DSF, colorScheme: "dark", locale: "en-US" });
const page = await ctx.newPage();

// ---------------- Scenario A: Ayu, suspicious international request
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await shot(page, "A00_landing", "Landing page before sign-in");
await signIn(page, "stu_ayu", "Ayu", "A01");
const chipA = page.locator("#req-samples .chip", { hasText: "Urgent deposit e-mail" });
await shot(page, "A02_request_tab", "Check a request tab, empty form", await box(chipA));
await chipA.click();
const checkBtn = page.locator("#req-check");
await shot(page, "A03_sample_loaded", "Synthetic sample 'Urgent deposit e-mail' loaded into the form", await box(checkBtn));
await checkBtn.click();
await page.locator("#req-result .verdict").waitFor();
await scrollTo(page, "#req-result .verdict");
await shot(page, "A04_verdict", "Real verdict: Stop. Do not pay through this request (CONFLICT, HOLD_DO_NOT_PAY)");
const showMail = page.getByRole("button", { name: "Show the e-mail" });
await scrollToText(page, "What to do now");
await shot(page, "A05_next_steps", "What to do now: checklist and registry contact", await box(showMail));
await showMail.click();
await scrollToText(page, "Official contact", 120);
await shot(page, "A06_draft", "Draft e-mail to the registry contact (not sent)");
await scrollToText(page, "What we checked");
await shot(page, "A07_checks", "What we checked: sender, link, payee, account, SWIFT");
await scrollToText(page, "Warning signs");
await shot(page, "A08_warnings", "Warning signs in the message");
await scrollTo(page, "#req-result .locked", 300);
await shot(page, "A09_locked", "Cost comparison and payment plan locked");
await full(page, "A_full", "Full Scenario A result page");
const caseA = (await page.locator("#req-result .code-chip").nth(2).textContent()).trim();
const csrfA = await page.evaluate(async () => (await (await fetch("/api/session/me")).json()).csrf_token);
const r409 = await page.evaluate(async ([cid, csrf]) => {
  const r = await fetch(`/api/cases/${cid}/plan/propose`, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: "{}" });
  return { status: r.status, body: await r.text() };
}, [caseA, csrfA]);
manifest.api.push({ label: "Ayu proposes a plan on the held case", method: "POST", path: `/api/cases/${caseA}/plan/propose`, ...r409 });

// Prompt injection sample (D2) for the security scene
await page.evaluate(() => window.scrollTo(0, 0));
await page.locator("#req-samples .chip", { hasText: "Hidden instructions" }).click();
await page.locator("#req-check").click();
await page.waitForFunction(() => document.querySelector("#req-result .verdict h2")?.textContent.includes("warning signs"));
await scrollTo(page, "#req-result .verdict");
await shot(page, "D2_injection_hold", "Prompt-injection sample: details match but the payment is held");
await signOut(page);

// ---------------- Scenario B: Budi, slips vs ledger
await signIn(page, "stu_budi", "Budi", "B01");
const slipsTab = page.locator('button.tab[data-tab="slips"]');
await shot(page, "B02_tabs", "Student tabs after sign-in", await box(slipsTab));
await slipsTab.click();
const sampleB = page.locator("#slip-sample");
await shot(page, "B03_slips_tab", "Did my payment arrive? tab", await box(sampleB));
await sampleB.click();
await scrollTo(page, "#slip-rows", 140);
const slipCheck = page.locator("#slip-check");
await shot(page, "B04_slips_loaded", "Bank-agent offer and three synthetic slips loaded", await box(slipCheck));
await slipCheck.click();
await page.locator("#slip-result .verdict").waitFor();
await scrollTo(page, "#slip-result .verdict");
await shot(page, "B05_verdict", "Real verdict: 1 of 3 payments confirmed by the university record");
const cards = page.locator("#slip-result .slip-card");
for (let i = 0; i < 3; i++) {
  await page.evaluate((i) => { const c = document.querySelectorAll("#slip-result .slip-card")[i]; window.scrollTo({ top: c.getBoundingClientRect().top + window.scrollY - 40, behavior: "instant" }); }, i);
  await shot(page, `B06_slip_${i + 1}`, `Slip card ${i + 1}: slip, bank feed, institution ledger timeline`);
}
await scrollToText(page, "Warning signs");
await shot(page, "B07_warnings", "Warning signs in the bank-agent offer");
await full(page, "B_full", "Full Scenario B result page");
await signOut(page);

// ---------------- Scenario C: Citra, matched request, quotes, plan
await signIn(page, "stu_citra", "Citra", "C01");
const chipC = page.locator("#req-samples .chip", { hasText: "Official invoice e-mail" });
await chipC.click();
const checkC = page.locator("#req-check");
await shot(page, "C02_sample_loaded", "Synthetic sample 'Official invoice e-mail' loaded", await box(checkC));
await checkC.click();
await page.locator("#req-result .verdict.allow").waitFor();
await scrollTo(page, "#req-result .verdict");
await shot(page, "C03_verdict", "Real verdict: matches the official procedure on record (MATCHED_SOURCE)");
await scrollToText(page, "What we checked");
await shot(page, "C04_checks", "All checks match the synthetic registry");
await scrollToText(page, "Compare transfer costs");
const compareBtn = page.getByRole("button", { name: "Compare total cost" });
await shot(page, "C05_quotes_form", "Two illustrative quotes entered", await box(compareBtn));
await compareBtn.click();
await page.locator("#req-result .result-grid").waitFor();
await scrollTo(page, "#req-result .result-grid", 120);
await shot(page, "C06_quotes_result", "Decimal all-in cost comparison, lowest total cost badge");
await scrollToText(page, "Sandbox payment plan");
const prepare = page.getByRole("button", { name: "Prepare a sandbox plan" });
await shot(page, "C07_plan_choose", "Sandbox payment plan: choose quote", await box(prepare));
await prepare.click();
await page.getByRole("button", { name: "Approve this plan" }).waitFor();
await scrollToText(page, "Sandbox payment plan");
const approve = page.getByRole("button", { name: "Approve this plan" });
await page.evaluate(() => window.scrollBy(0, 120));
await shot(page, "C08_plan_proposed", "Plan proposed, waiting for the student's decision", await box(approve));
await approve.click();
await page.locator("#req-result .plan-approved").waitFor();
await scrollToText(page, "Sandbox payment plan");
await shot(page, "C09_plan_approved", "Approved by the student, not executed");
await page.locator("#req-result details.tech summary").click();
await scrollTo(page, "#req-result details.tech", 40);
await shot(page, "C10_audit", "Technical record: hash-chained audit events");
await full(page, "C_full", "Full Scenario C result page");
const caseC = (await page.locator("#req-result .code-chip").nth(2).textContent()).trim();
const csrfC = await page.evaluate(async () => (await (await fetch("/api/session/me")).json()).csrf_token);
const plan = await page.evaluate(async (cid) => (await (await fetch(`/api/cases/${cid}`)).json()).plans.at(-1), caseC);
const body = JSON.stringify({ plan_revision: plan.revision, plan_digest: plan.digest });
const replay = await page.evaluate(async ([cid, csrf, b]) => {
  const r = await fetch(`/api/cases/${cid}/plan/approve`, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": "video-other-key-0001" }, body: b });
  return { status: r.status, body: await r.text() };
}, [caseC, csrfC, body]);
manifest.api.push({ label: "Citra approves again with a new key", method: "POST", path: `/api/cases/${caseC}/plan/approve`, ...replay });
const noCsrf = await page.evaluate(async (cid) => {
  const r = await fetch(`/api/cases/${cid}/analyze`, { method: "POST" });
  return { status: r.status, body: await r.text() };
}, caseC);
manifest.api.push({ label: "State change without the CSRF header", method: "POST", path: `/api/cases/${caseC}/analyze`, ...noCsrf });
await signOut(page);

// ---------------- Security: cross-user, reviewer, anonymous
await signIn(page, "stu_ayu", "Ayu", "S01");
const crossUser = await page.evaluate(async (cid) => { const r = await fetch(`/api/cases/${cid}`); return { status: r.status, body: await r.text() }; }, caseC);
manifest.api.push({ label: "Ayu opens Citra's case", method: "GET", path: `/api/cases/${caseC}`, ...crossUser });
await signOut(page);
await signIn(page, "officer_nbu", "Finance office", "S02");
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await page.locator("#office-list .case-item").first().waitFor();
await shot(page, "S03_office_inbox", "Office reviewer inbox: escalated cases, read-only");
const csrfO = await page.evaluate(async () => (await (await fetch("/api/session/me")).json()).csrf_token);
const officer = await page.evaluate(async ([cid, csrf, b]) => {
  const r = await fetch(`/api/cases/${cid}/plan/approve`, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": "video-officer-0001" }, body: b });
  return { status: r.status, body: await r.text() };
}, [caseC, csrfO, body]);
manifest.api.push({ label: "Office reviewer tries to approve a student's plan", method: "POST", path: `/api/cases/${caseC}/plan/approve`, ...officer });
await signOut(page);
const anon = await ctx.request.get(`${BASE}/api/cases/${caseC}`);
manifest.api.push({ label: "No session", method: "GET", path: `/api/cases/${caseC}`, status: anon.status(), body: await anon.text() });

await browser.close();
manifest.gitCommit = execSync("git rev-parse HEAD", { cwd: new URL("../../", import.meta.url).pathname }).toString().trim();
writeFileSync(OUT + "manifest.json", JSON.stringify(manifest, null, 2));
console.log("API results:");
for (const a of manifest.api) console.log(`  ${a.status} ${a.method} ${a.path}  (${a.label})`);
console.log(`Saved ${manifest.shots.length} captures to ${OUT}`);
