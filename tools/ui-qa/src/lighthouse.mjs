// Lighthouse lab runs (mobile and desktop presets) on the running CEKBAO app.
// Lab data only: it does not measure field performance (CrUX / real users).
// The demo session cookie is passed as a header and removed from the saved reports.
import { chromium } from "playwright";
import lighthouse from "lighthouse";
import * as chromeLauncher from "chrome-launcher";
import desktopConfig from "lighthouse/core/config/desktop-config.js";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8780";
const OUT = path.resolve(process.cwd(), "../../evidence/policyguard/ui/lighthouse");
fs.mkdirSync(OUT, { recursive: true });

async function sessionAndCase() {
  const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || "chrome" });
  const page = await browser.newPage();
  await page.goto(`${BASE}/check/sign-in`);
  await page.getByLabel("User ID").fill("pg_payer");            // sandbox test value (fixture)
  await page.getByLabel("Access code").fill("demo-payer-2026");  // sandbox test value (fixture)
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/check$/);
  await page.goto(`${BASE}/check?example=policy_change`);
  await page.getByRole("button", { name: "Check instructions" }).click();
  await page.waitForURL(/\/check\/cases\//);
  await page.locator("h1.decision-label").waitFor({ timeout: 30000 });
  const caseUrl = page.url().split("#")[0];
  const cookie = (await page.context().cookies()).find((c) => c.name === "cekbao_session");
  await browser.close();
  return { cookie: `${cookie.name}=${cookie.value}`, token: cookie.value, caseUrl };
}

const { cookie, token, caseUrl } = await sessionAndCase();
const targets = [["public-landing", `${BASE}/`, false], ["sign-in", `${BASE}/check/sign-in`, false], ["check-form", `${BASE}/check`, true],
                 ["result-policy-change", caseUrl, true]];
const chrome = await chromeLauncher.launch({ chromePath: chromium.executablePath() === "" ? undefined : undefined,
                                             chromeFlags: ["--headless=new"] });
const summary = [];
try {
  for (const [name, url, auth] of targets) {
    for (const preset of ["mobile", "desktop"]) {
      const flags = { port: chrome.port, output: ["html", "json"], logLevel: "error",
                      extraHeaders: auth ? { Cookie: cookie } : undefined,
                      onlyCategories: ["performance", "accessibility", "best-practices", "seo"] };
      const result = await lighthouse(url, flags, preset === "desktop" ? desktopConfig : undefined);
      const [html, json] = result.report.map((r) => r.split(token).join("[redacted-session]"));
      fs.writeFileSync(path.join(OUT, `${name}-${preset}.report.html`), html);
      fs.writeFileSync(path.join(OUT, `${name}-${preset}.report.json`), json);
      const lhr = result.lhr;
      const score = (k) => Math.round((lhr.categories[k]?.score ?? 0) * 100);
      summary.push({ page: name, preset, url: url.replace(BASE, ""), fetched_at: lhr.fetchTime,
        lighthouse: lhr.lighthouseVersion, user_agent: lhr.environment.hostUserAgent,
        throttling: lhr.configSettings.throttlingMethod, form_factor: lhr.configSettings.formFactor,
        performance: score("performance"), accessibility: score("accessibility"),
        best_practices: score("best-practices"), seo: score("seo"),
        lcp_ms: Math.round(lhr.audits["largest-contentful-paint"].numericValue),
        cls: Number(lhr.audits["cumulative-layout-shift"].numericValue.toFixed(3)),
        tbt_ms: Math.round(lhr.audits["total-blocking-time"].numericValue) });
    }
  }
} finally {
  await chrome.kill();
}
fs.writeFileSync(path.join(OUT, "summary.json"), JSON.stringify(summary, null, 2));
for (const s of summary) {
  console.log(`${s.page.padEnd(22)} ${s.preset.padEnd(8)} perf ${s.performance} a11y ${s.accessibility} ` +
              `bp ${s.best_practices} seo ${s.seo} LCP ${s.lcp_ms}ms CLS ${s.cls} TBT ${s.tbt_ms}ms`);
}
