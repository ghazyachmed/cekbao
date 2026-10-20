# CEKBAO pitch outline (10 slides, 10 minutes or less)

Rules for every slide: one message per slide; every number has its source and date on the slide; only implemented features appear as "works today"; synthetic data is labelled; no "first", "only", "fraud-free", "bank verified" or partner claims.

Suggested timing: about 55 seconds per slide, plus 1 minute of live demo inside slide 5.

---

### Slide 1. Title (0:00 to 0:30)

- **CEKBAO | Student Payment Verification Agent**
- "Check the request. Use the official payment route." 学费支付核验助手
- Team HMIF: Ghazy Achmed Movlech Urbayani, M Azzam Robbani. Topic C: Cross-border & Student Finance Assistant.
- Small print: CEKBAO = Indonesian "cek" + Mandarin 保 (protect). Coined name.

Speaker note: "Students pay large, one-time amounts to institutions they have never visited. CEKBAO checks the request before any money moves."

### Slide 2. The problem is real and specific (0:30 to 1:30)

- Singapore Police Force, 19 Mar 2026: at least 20 cases, at least S$31,000 lost since March 2026. E-mails impersonate educational institutions and demand urgent fee transfers.
- UMTS, Indonesia, Feb 2025: about 273 students used an unofficial "pay tuition without hassle" service. 28 slips, only 6 matching bank transactions (detikSumut, Kompas). Victims were domestic.
- IEEE S&P 2026 study (48 surveyed, 9 interviewed, US): international students face impersonation scams and do not know which resources to trust.

Footer: "Case figures. Not national rates." Speaker note: do not extrapolate.

### Slide 3. Where current tools stop (1:30 to 2:30)

- Payment rails (for example Flywire) move money safely once the student is on the right rail.
- Scam screeners (for example ScamShield) classify messages and links.
- Gap we test: nothing in the student's flow compares *this* request with *this* university's documented procedure, or checks that a slip reached the university's own record.
- Show the matrix from `docs/MARKET_EVIDENCE.md` section 3 (compact).

Speaker note: "We complement them. We do not replace them."

### Slide 4. How CEKBAO works (2:30 to 3:30)

Four steps, one line each:

1. Read: sanitize, redact, extract (rules, or an optional LLM that sees only redacted text).
2. Compare: sender, links, payee, account, SWIFT, method and rules against a curated registry.
3. Decide: deterministic gate. Any conflict or unknown means HOLD_DO_NOT_PAY.
4. Act: checklist, draft to the official office, quote comparison, sandbox plan only after explicit approval.

Visual: the architecture diagram from `docs/TECHNICAL.md` (two layers).

### Slide 5. Live demo: suspicious request (3:30 to 5:00)

- Scenario A in the app. Verdict: "Stop. Do not pay through this request." 7 mismatches. Look-alike sender, third-party payee, Hong Kong SWIFT for a US university, visa threat, discount.
- Show "What to do now" with the registry contact and the draft e-mail (not sent).
- Show that the payment plan is locked.

### Slide 6. A slip is not proof (5:00 to 6:00)

- Scenario B (UMTS-inspired, all data invented): "1 of 3 payments confirmed by the university record."
- Timeline per slip: slip says, bank shows, university record shows.
- A PDF that says "LUNAS / PAYMENT SUCCESSFUL" stays PAYMENT_UNCONFIRMED.

### Slide 7. When the request is right (6:00 to 7:00)

- Scenario C: green verdict, but "a record comparison, not a bank check".
- Two user-provided quotes: IDR 8,316,125.00 vs IDR 8,255,000.00, unknown intermediary fees disclosed (illustrative numbers).
- Plan approved once with an idempotency key. Status: "Approved by you, not executed".

### Slide 8. Security and compliance (7:00 to 8:00)

- Permission tiers: anonymous, student (own cases only), office reviewer (escalated, read-only), LLM (read-only tool, no authority).
- Adversarial results: prompt injection holds, spoofed subdomain conflicts, cross-user 404, reviewer approval 403, no session 401, duplicate approval runs once.
- 117 automated tests pass. 18 of 18 scenario expectations pass (20 Oct 2026).
- Known risks: synthetic registry, demo sign-in, live LLM not verified.

### Slide 9. Evidence, not claims (8:00 to 9:00)

- Synthetic evaluation, 10 messages and 6 slips: keyword baseline cleared 6 of 8 unsafe messages and accepted 4 slips without a record. CEKBAO held 8 of 8 and accepted 0 slips without a record.
- Caveat on the slide: same authors wrote fixtures and rules. Not real-world accuracy. Not a user study.
- Evidence bundle: hash-chained audit, reproducible export, every finding cites its registry source.

### Slide 10. What we need to learn next (9:00 to 10:00)

- Hypothesis buyer: university international or finance office. No pilot or contract yet.
- Next 8 weeks: student interviews, 3 office conversations, usability test, live LLM evaluation against the rules-only baseline.
- Ask: one university office willing to publish a verified payment-procedure record for a pilot.
- Close with the tagline.

---

Before presenting: re-check source 4 (FBI alert) if you cite it. Record the demo per `docs/DEMO_STORYBOARD.md` as a backup in case the live demo fails.
