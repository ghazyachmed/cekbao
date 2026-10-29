# CEKBAO design system: payment instruction check

Scope: the PolicyGuard pages served at `/check` and `/review` (FastAPI + Jinja2 SSR, vanilla JS for progressive enhancement). Tokens: `policyguard/web/static/tokens.css`. Components: `policyguard/web/static/app.css`. Strings: `policyguard/web/messages/en.json`.

## 0. Visual direction (defined before the comparison work)

CEKBAO's job is to examine a payment instruction against institutional evidence. The defining interaction is therefore a **side-by-side comparison**: what the instruction asks for, what the applicable policy states, and a verdict per field (agrees, conflicts, not stated), followed by what remains unknown and the next step. It is a ledger-like table, not a dashboard: no metric tiles, no identical card grids, no trust badges.

- Reading order on the result page: decision headline, next action, comparison table ("Why"), decisive policy quote with its source and validity, then limits and history.
- One bold element: the decision headline. The comparison uses the semantic colours only in its status column, always with an icon and a word.
- Values that must be compared character by character (accounts, bank codes, amounts) use Inter with tabular, disambiguated digits so a single changed character is visible.
- On phones the table becomes one block per field, in the same order, with the column names repeated as labels; nothing scrolls sideways.
- Familiar patterns stay familiar: native form controls, radio cards, disclosure triangles, plain tables.
- Colour carries meaning only: teal for the one primary action, semantic tones for decision states, yellow dashed outlines only for synthetic data.

## 1. User tasks and information hierarchy

Primary question: "Does this payment instruction match the institution's applicable policy?"

| Task | Screen | What comes first |
|---|---|---|
| Enter the instruction, institution and dates | A. Check form (`/check`) | One column: instruction, institution, dates, optional document, one primary action |
| Review what was read | B. "What we read from the instruction" (result page) | Each field with its source (AI model with verified quote, fixed rules, or the user); missing fields say "Not found in the instruction". No confidence percentages |
| Wait for the check | C. Processing (`/check/cases/{id}`) | Backend state only: Queued, Checking, Retry scheduled, Completed, Could not finish |
| Understand the result | D. Result (same URL) | 1 headline, 2 next action, 3 why, 4 evidence, 5 limits and history |
| Inspect evidence | E. Evidence cards | Decisive quote visible; metadata behind a disclosure |
| Review as the institution | F. Review queue (`/review`, server-enforced role) | Table of checks needing review, then case evidence, history and a review form with a required reason |

Marketing content stays on the existing landing page (`/`). The check form is the app entry point after sign-in.

## 2. Typography

| Property | Value |
|---|---|
| Family | Inter variable (rsms/inter), SIL Open Font License 1.1, served from `/pg-static/fonts/` (from `@fontsource-variable/inter` 5.2.8). License: `policyguard/web/static/fonts/OFL-Inter.txt` |
| Why Inter | The repository referenced Lato in CSS but never loaded it. Inter has tabular figures, slashed zero and disambiguation alternates that matter for account numbers, and covers Latin, Latin Extended, Cyrillic, Greek and Vietnamese for international institution names |
| Character sets | Five subset files, loaded only when a page contains those characters (`unicode-range`) |
| Fallback | `"Inter Fallback"` (Arial with `size-adjust: 107.4%`, `ascent-override: 90.2%`, `descent-override: 22.48%`) to limit layout shift, then `system-ui` |
| Loading | Latin subset preloaded; `font-display: swap`. Measured CLS on audited pages: 0 (Lighthouse lab) |
| Body | 16 px / 26 px, weight 400 |
| Secondary text (hints, metadata) | 14 px / 21 px, weight 400, `--ink-2` |
| Labels | 16 px / 24 px, weight 620 |
| Section headings | 22 px / 30 px, weight 620, letter spacing -0.011 em |
| Page headings | `clamp(28px, 1.2rem + 1.6vw, 36px)`, line height 1.2, weight 720 |
| Decision headline | `clamp(28px, 1.3rem + 1.4vw, 34px)`, weight 720 (the one bold element on the page) |
| Account numbers, codes, amounts | Inter with `tnum`, `zero` (slashed zero), `cv05` (tailed l), `cv08` (serifed I) so 0/O and 1/l/I are distinct |
| Measure | Prose max 68 characters per line |

## 3. Spacing and layout

Spacing scale (px): 4, 8, 12, 16, 24, 32, 48, 64 (`--space-1` … `--space-8`).

| Element | Value |
|---|---|
| Page gutter | 16 px below 768 px, 32 px from 768 px |
| Form width | 720 px max (`--width-form`) |
| Workspace width | 1200 px max (`--width-workspace`) |
| Control height | 44 px design target (`--control-height`); large primary button 52 px |
| Radius | 6 px controls, 10 px buttons and choices, 14 px cards |

Responsive rules: one-column forms at every width; evidence cards stack; conflicting sources sit side by side from 960 px and stack below, in source order. Wide tables sit in a labelled, focusable scroll region. The header wraps; the product subtitle hides below 640 px. Long names and URLs wrap (`overflow-wrap: anywhere`, URLs `word-break: break-all`).

## 4. Semantic colors

Light theme only (`color-scheme: light`); dark mode is not implemented for these pages. Measured ratios for every pair the UI uses: `docs/policyguard/CONTRAST.md` (38 pairs, 0 failures, generated by `scripts/contrast_report.py`).

| Token | Hex | Meaning |
|---|---|---|
| `--canvas` / `--surface` / `--surface-sunken` | #f4f6f8 / #ffffff / #eef2f5 | Page, cards, quotes and table headers |
| `--ink` / `--ink-2` | #0b1b2b / #3c4d5e | Primary and secondary text |
| `--line` / `--line-control` | #d6dee5 / #6c7c8c | Decorative dividers / control boundaries (≥ 3:1) |
| `--primary` (+ hover, active, tint) | #0a6b5f | The only action accent (CEKBAO teal, deepened for contrast) |
| `--focus` | #1d5fd1 | 3 px focus outline, 2 px offset |
| ok / bad / warn / review | #0b6a3c, #a3161f, #7a4a00, #3a3d9c on tinted backgrounds | CONSISTENT / CONFLICT / INSUFFICIENT_EVIDENCE / REQUIRES_REVIEW. Always with an icon and words |
| info | #0b5394 | Processing status, translation labels |
| synthetic | #5a4500 on #fff6cc, dashed border | Every synthetic institution, example and the global banner |

Colour is never the only signal: each decision has a distinct icon (check, octagon, triangle, person) and a sentence.

## 5. Components and states

| Component | States |
|---|---|
| Primary button | default, hover (`--primary-hover`), active, focus (outline), busy (`aria-disabled`, label "Saving your check…", progress cursor; the server's idempotency key prevents duplicates) |
| Secondary / quiet button | default, hover tint, focus |
| Text input, textarea, select | default boundary 1 px `--line-control`, hover darker, focus outline, invalid (2 px `--bad-line`, `aria-invalid`, message above the field, linked from the error summary) |
| Date input | as above; Chrome focuses an inner segment, so the outline uses `:focus-within` |
| Choice (radio card) | default, hover, checked (2 px primary border, tint), focus (outline on the card) |
| Error summary | `role="alert"`, receives focus on load, links to each field |
| Banners | info, warning (rate limit, storage failure, form reused, stale review), success (review recorded) |
| Upload | idle drop zone, dragging, uploading (native `<progress>` with real byte counts), clean, rejected (reason, Try again, Remove), network failure (Try again, Remove) |
| Processing status | info (queued, checking), warning (retry scheduled with the time), error (could not finish: "technical failure, not a judgment") |
| Decision banner | four tones listed above |
| Evidence card | applied, superseded (earlier version, sunken), conflicting (review border), unauthorized (warning border), translation block (dashed info border, explicit label) |
| Disclosure (`<details>`) | closed, open, focus |

## 6. Accessibility requirements (WCAG 2.2 AA target)

Semantic HTML first: landmarks (`header`, `nav`, `main`, `footer`), one `h1` per page, `fieldset`/`legend` for groups, persistent `label`s, skip link to `#main`. Errors: summary with links plus inline messages via `aria-describedby`. Status changes: one polite live region that announces only state changes, not every poll. After a completed check the result headline receives focus. Reduced motion: no animation; the only transitions (button colour, 120 ms) are removed under `prefers-reduced-motion`. Targets: 44 px controls as a design target; WCAG 2.2 SC 2.5.8 requires 24 px minimum, which all controls exceed. Evidence: `evidence/policyguard/ui/` (axe-core, keyboard run, screenshots) and section 10.

## 7. Interaction and motion

No continuous animation, no countdowns, no invented progress percentages. Polling: 1 s, ×1.5 backoff to 8 s, ±20 % jitter, stops after 40 polls with a "taking longer" message. Pages work without JavaScript (radio list instead of filtering, server-side upload with the form, refresh link instead of polling). Form drafts are never stored in browser storage; after an expired session the text is carried in the re-rendered sign-in page only.

## 8. Verification-specific content rules

1. Decision labels are fixed: "Matches the checked policy." / "Conflicts with the checked policy." / "Not enough evidence to verify." / "Institution review required."
2. Every result says that a policy match does not confirm payment safety or settlement, and that payment status is unknown. "Safe to pay" never appears (tested).
3. Technical failure is not a verdict: provider outages complete with fixed rules and a limitation, or show "Could not finish … not a judgment about the instruction".
4. "Effective from" (validity) and "Retrieved on" (fetch time) are separate fields; validity intervals say "(not including …)" for the end date.
5. Original-language evidence is shown with `lang`; translations carry "Translation (unofficial, provided by CEKBAO; the original is the authoritative text)".
6. Unverified URLs from instructions are never links. Next-action links go only to the institution's registered contact page; synthetic addresses are marked "Synthetic address; not a real website".
7. Dates use month names ("15 November 2026"); time zones are shown; currencies use ISO codes.
8. Limitations explain consequences ("The AI model was not used for this check … read with fixed rules").

## 9. Skills and references used

| Source | Commit | Status | How it was used |
|---|---|---|---|
| anthropics/skills `skills/frontend-design/SKILL.md` | dbd4588 | read, applied | One bold element (decision headline), subject-grounded type detail (account-number glyphs), avoided generic tells (no all-caps eyebrows, no middle-dot meta strings, no gradient cards), copy from the user's side |
| vercel-labs/agent-skills `skills/web-design-guidelines/SKILL.md` | 1a2c79d | read; rules applied through the audit below | The skill fetches a live rule list; this project used axe-core and manual checks instead of its file:line report |
| vercel-labs/agent-skills `react-best-practices` | 1a2c79d | read, not applicable to the app (no React); React is used only in the Remotion video |
| nextlevelbuilder/ui-ux-pro-max-skill `.claude/skills/ui-ux-pro-max/SKILL.md` | 28b3b8d | read, priorities applied (accessibility and touch first); its search scripts were not executed |
| VoltAgent/awesome-design-md `design-md/wise/DESIGN.md` | 3b60532 | read as reference only | Hierarchy, single-column focused forms, 16/24 body rhythm. Wise branding, lime colour, fonts and copy were not used |
| obra/superpowers `test-driven-development`, `verification-before-completion` | 2ce8aa1 | read, applied | Red then green for each feature; claims only with evidence |
| remotion-dev/skills `remotion-best-practices`, local `remotion-markup` | 30d4553 | read, applied to the video | `@remotion/media`, frame-driven animation, `useVideoConfig` timing |
| ashishps1/awesome-low-level-design, donnemartin/system-design-primer | 31595db, ae9bbd7 | reference collections (not agent skills) | Ports and adapters, strategy, repository, state machine, outbox, idempotency patterns |

## 10. Verification status

| Item | Result | Evidence |
|---|---|---|
| Behavioural tests (web) | 21 passed | `tests/pgtests/test_web.py` |
| axe-core 4.13.0 (WCAG 2.0/2.1/2.2 A and AA tags) at 375 and 1440 px, 10 page states | 0 violations | `evidence/policyguard/ui/axe/`, `audit-summary.json` |
| Horizontal overflow at 320, 375, 768, 1024, 1440 px | 0 pages after fixes (the 320 px form overflowed by 28 px before the fix) | `audit-summary.json`, `screens/` |
| Keyboard-only main journey (sign in, choose example, submit, result focused) | completed; every focus stop shows a visible outline (2 date inputs lacked one before the `:focus-within` fix) | `audit-summary.json` → `keyboard_flow` |
| Lighthouse 13.5 lab, mobile and desktop presets | App pages: Performance 100, Accessibility 100, Best Practices 100, SEO 63 (deliberately `noindex`). Public landing `/`: Performance 100, Accessibility 100, Best Practices 96, SEO 100 after fixing an invalid relative sitemap URL in robots.txt and adding a meta description | `evidence/policyguard/ui/lighthouse/` |
| Screenshot review, desktop 1440 and mobile 375/320 (internal walkthrough, not user research) | Found and fixed: comparison caption rendered one character per line at 375 px (axe did not catch it); row headers kept a 9rem width on mobile; example select overflowed by 28 px at 320 px; wordmark broke as "CEKBA/O"; two date inputs had no visible focus outline; "0 not stated" noise in the summary. All screens captured again after the fixes | `evidence/policyguard/ui/screens/` |
| Screen reader (VoiceOver/NVDA) | not tested | — |
| 200 % zoom and 400 % reflow | 320 px width covers 400 % reflow of 1280 px; 200 % zoom not separately tested | — |
| Usability sessions with participants | not done; no participants were available. No user-research claims are made | — |
| Field Web Vitals (p75 LCP/INP/CLS) | not measured (no real users) | — |
