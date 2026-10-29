// UI audit against the running CEKBAO app (synthetic data only).
// Produces: responsive screenshots, axe-core results, a keyboard-only run of the main flow, overflow checks.
// Usage: BASE_URL=http://127.0.0.1:8780 npm run audit   (start the app with scripts/policyguard_serve.sh)
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8780";
const OUT = path.resolve(process.cwd(), "../../evidence/policyguard/ui");
const WIDTHS = [320, 375, 768, 1024, 1440];
const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
// Demo access codes are sandbox test values from policyguard/fixtures/demo_users.json.
const USERS = { payer: ["pg_payer", "demo-payer-2026"], reviewer: ["pg_reviewer", "demo-reviewer-2026"] };

for (const d of ["screens", "axe"]) fs.mkdirSync(path.join(OUT, d), { recursive: true });

async function signIn(page, [user, code]) {
  await page.goto(`${BASE}/check/sign-in`);
  await page.getByLabel("User ID").fill(user);
  await page.getByLabel("Access code").fill(code);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/check$|\/review/);
}

async function runExample(page, key) {
  await page.goto(`${BASE}/check?example=${key}`);
  await page.getByRole("button", { name: "Check instructions" }).click();
  await page.waitForURL(/\/check\/cases\//);
  const url = page.url().split("#")[0];
  await page.locator("h1.decision-label").waitFor({ timeout: 30000 });
  return url;
}

async function shoot(page, name, url, results) {
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(url);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    const file = `screens/${name}-${width}.png`;
    await page.screenshot({ path: path.join(OUT, file), fullPage: true });
    const entry = { page: name, width, horizontal_overflow_px: overflow, screenshot: file };
    if (width === 375 || width === 1440) {
      const axe = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
      fs.writeFileSync(path.join(OUT, `axe/${name}-${width}.json`), JSON.stringify({
        url: url.replace(BASE, ""), width, testEngine: axe.testEngine, violations: axe.violations,
        incomplete: axe.incomplete.map((i) => ({ id: i.id, impact: i.impact, help: i.help, nodes: i.nodes.length })),
        passes: axe.passes.length }, null, 2));
      entry.axe_violations = axe.violations.map((v) => `${v.id} (${v.impact}, ${v.nodes.length})`);
      entry.axe_incomplete = axe.incomplete.length;
    }
    results.push(entry);
  }
}

async function keyboardFlow(browser) {
  // Complete the main journey with the keyboard only and record every focus stop.
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const stops = [];
  const record = async () => stops.push(await page.evaluate(() => {
    const el = document.activeElement;
    const style = getComputedStyle(el);
    const label = el.labels && el.labels[0] ? el.labels[0].innerText : "";
    return { tag: el.tagName, id: el.id, name: (el.getAttribute("aria-label") || label || el.innerText || el.value || "").trim().slice(0, 60),
      outline: `${style.outlineStyle} ${style.outlineWidth}`, url: location.pathname };
  }));
  await page.goto(`${BASE}/check/sign-in`);
  await page.keyboard.press("Tab"); await record();                    // skip link
  for (let i = 0; i < 12 && !(await page.evaluate(() => document.activeElement.id === "user_id")); i++) {
    await page.keyboard.press("Tab"); await record();
  }
  await page.keyboard.type(USERS.payer[0]);
  await page.keyboard.press("Tab"); await record();
  await page.keyboard.type(USERS.payer[1]);
  await page.keyboard.press("Enter");
  await page.waitForURL(/\/check$/);
  // Choose the synthetic example with the keyboard.
  for (let i = 0; i < 20 && !(await page.evaluate(() => document.activeElement.id === "example")); i++) {
    await page.keyboard.press("Tab"); await record();
  }
  await page.keyboard.press("ArrowDown");                               // second example: policy change
  await page.keyboard.press("Tab"); await record();
  await page.keyboard.press("Enter");
  await page.waitForURL(/example=/);
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab"); await record();
    if (await page.evaluate(() => document.activeElement.type === "submit" && document.activeElement.closest("#check-form"))) break;
  }
  await page.keyboard.press("Enter");
  await page.waitForURL(/\/check\/cases\//);
  await page.locator("h1.decision-label").waitFor({ timeout: 30000 });
  await page.waitForTimeout(300);
  const focusedAfterResult = await page.evaluate(() => document.activeElement.id);
  const headline = await page.locator(".decision-label").first().innerText();
  await ctx.close();
  const invisible = stops.filter((s) => s.outline.startsWith("none") && s.tag !== "BODY");
  return { completed: true, headline, focused_after_result: focusedAfterResult, focus_stops: stops.length,
           stops_without_visible_outline: invisible, stops };
}

const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || "chrome" });
const results = [];
try {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(`${BASE}/check/sign-in`);
  await shoot(page, "sign-in", `${BASE}/check/sign-in`, results);
  await signIn(page, USERS.payer);
  await shoot(page, "check-form", `${BASE}/check`, results);

  // Error state: submit an empty form.
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.goto(`${BASE}/check`);
  await page.getByRole("button", { name: "Check instructions" }).click();
  await page.locator("#error-summary").waitFor();
  await page.screenshot({ path: path.join(OUT, "screens/check-errors-1024.png"), fullPage: true });
  results.push({ page: "check-errors", width: 1024, screenshot: "screens/check-errors-1024.png",
                 focused: await page.evaluate(() => document.activeElement.id) });

  // Upload rejection and recovery controls.
  await page.goto(`${BASE}/check`);
  await page.setInputFiles("#document_input", { name: "invoice.pdf", mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 1 0 obj<</S /JavaScript /JS (x)>>endobj") });
  await page.locator(".upload-item.is-rejected").waitFor();
  await page.locator("#document").screenshot({ path: path.join(OUT, "screens/upload-rejected-1024.png") });
  results.push({ page: "upload-rejected", width: 1024, screenshot: "screens/upload-rejected-1024.png",
                 text: await page.locator(".upload-item").innerText() });

  // Processing state right after submission (captured before the worker finishes, when it is still queued).
  await page.goto(`${BASE}/check?example=conflict`);
  await page.getByRole("button", { name: "Check instructions" }).click();
  await page.waitForURL(/\/check\/cases\//);
  await page.screenshot({ path: path.join(OUT, "screens/processing-1024.png") });
  results.push({ page: "processing", width: 1024, screenshot: "screens/processing-1024.png",
                 status: await page.locator(".status-label, .decision-label").first().innerText() });

  const cases = {};
  for (const key of ["conflict", "policy_change", "insufficient", "source_conflict"]) cases[key] = await runExample(page, key);
  for (const [key, url] of Object.entries(cases)) await shoot(page, `result-${key}`, url, results);
  await shoot(page, "history", `${BASE}/check/history`, results);

  const rctx = await browser.newContext();
  const rpage = await rctx.newPage();
  await signIn(rpage, USERS.reviewer);
  await shoot(rpage, "review-queue", `${BASE}/review`, results);
  await shoot(rpage, "review-case", cases.source_conflict.replace("/check/cases/", "/review/cases/"), results);

  const keyboard = await keyboardFlow(browser);
  const summary = { generated_at: new Date().toISOString(), base_url: BASE, data: "synthetic", widths: WIDTHS,
    axe_tags: AXE_TAGS, results, keyboard_flow: keyboard,
    overflow_failures: results.filter((r) => r.horizontal_overflow_px > 0),
    axe_failures: results.filter((r) => r.axe_violations && r.axe_violations.length) };
  fs.writeFileSync(path.join(OUT, "audit-summary.json"), JSON.stringify(summary, null, 2));
  console.log(`screens: ${results.length}, overflow failures: ${summary.overflow_failures.length}, ` +
              `axe pages with violations: ${summary.axe_failures.length}, keyboard flow: ${keyboard.headline}, ` +
              `focus after result: ${keyboard.focused_after_result}, stops without outline: ${keyboard.stops_without_visible_outline.length}`);
  for (const f of summary.axe_failures) console.log("AXE", f.page, f.width, f.axe_violations.join("; "));
  for (const f of summary.overflow_failures) console.log("OVERFLOW", f.page, f.width, f.horizontal_overflow_px);
} finally {
  await browser.close();
}
