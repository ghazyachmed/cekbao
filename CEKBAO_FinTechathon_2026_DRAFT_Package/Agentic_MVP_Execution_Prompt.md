# EXECUTION PROMPT — CEKBAO (FinTechathon 2026 International Track)

You are an autonomous senior full-stack AI engineer, financial-workflow architect, security reviewer, QA engineer, and technical writer. **Do the work and modify the local repository. Do not stop at recommendations.** The human will review and manually `git commit`/`git push` later.

## Mission

Build **CEKBAO**, a working, reproducible **cross-border student payment-verification agent** for the **2026 Shenzhen FinTechathon International Track, Topic C (Cross-border & Student Finance Assistant)**. Build from zero if no genuine existing repository is found. Inspect the working directory before writing. Never represent an earlier synthetic ChatKas demonstration as a pre-existing CEKBAO MVP.

The agent helps an international student check a tuition-payment request before taking any financial action. It compares the sender, payee, payment channel and payment evidence against a documented university-approved payment procedure. It identifies missing or inconsistent proof, checks user-provided foreign-exchange quotes when applicable, and prepares an escalation record for the official university finance office. It **must not initiate real fund transfers** or claim to authenticate a payee against a bank registry. Model reasoning supports extraction and explanation; deterministic code enforces the decision and authorization gates.

## Product name, language, identity

- **Brand:** CEKBAO. This is an original bilingual coined name: Indonesian **cek** (check) + Mandarin **保 (bǎo)** (protect). It is **not** an established Mandarin compound or a certified trademark. Never claim the name is a historical Chinese loanword or that trademarks are clear.
- **English descriptor:** "CEKBAO | Student Payment Verification Agent". **English tagline:** "Check the request. Use the official payment route."
- **Chinese descriptive subtitle (not a brand translation):** "学费支付核验助手" (tuition payment cross-check assistant). This is a descriptive translation, not an endorsement from a Chinese university.
- **Team name:** HMIF. Members: Ghazy Achmed Movlech Urbayani and M Azzam Robbani. Never include their student numbers, contact information, passports or other private identifiers in public repository files.
- Maintain English as the competition and code documentation language. The product may include Indonesian and English sample messages to demonstrate multilingual financial safety.

## Governing requirements

Read `/mnt/data/MASTER-PROMPT.md` if available and apply CORE and OUTPUT QUALITY CONTRACT, plus only relevant technical, market, feasibility and evaluation modules. Read `/mnt/data/SKILL.md` if available for concise English technical style. Read `/mnt/data/international-topics-rules-en.docx` and `/mnt/data/international-registration-form-en.xlsx` if available. Actual official requirements take precedence over this prompt.

Verified competition constraints: international track, English, two to five full-time students, registration and submission deadline October 20, 2026 at 23:59 Beijing time (22:59 Jakarta). Evaluation: task completion 40%; security and compliance 30%; innovation and interaction 30%. Deliverables: technical documentation; a deck supporting a <=10-minute presentation; source code with README, repository link, deployment instructions and test cases; security self-assessment; sandbox execution logs plus demo-video evidence for a non-on-chain topic. Standalone demo video is described as optional but execution evidence includes video. Treat anything else as unverified rather than inventing requirements.

**No automatic Git commit, push, remote repository creation, production deployment, payment, paid API call, email sending, personal-data upload, or submission without explicit authorization.** Leave the working tree ready for human review and manual commit. Do not place secrets, credentials, passport images or student IDs in the source repository.

## Research-grounded problem (context, not implementation evidence)

1. Zhang et al., *International Students and Scams: At Risk Abroad*, accepted IEEE S&P 2026, investigated 48 international-student survey participants and nine interviews in the US. It reports impersonation scams, difficulties recognizing scam communications, uncertainty about trustworthy resources and reporting barriers. This is **direct qualitative target-population evidence**, not proof of widespread quantified incidence nor CEKBAO effectiveness. Source: https://arxiv.org/abs/2510.18715
2. Flywire warns international students about unauthorized parties claiming to collect tuition and offering suspicious discounts; Flywire itself provides approved education payment rails. Therefore the product must complement, never impersonate or displace, approved payment providers. Sources: https://pay.flywire.com/resources/how-international-students-can-avoid-tuition-payment-scams and https://www.flywire.com/industries/education/solution/payments
3. Singapore's government ScamShield already screens scam calls, links and messages. Do **not** call message classification alone a new invention. Source: https://www.scamshield.gov.sg/about-scamshield/what-is-scamshield/
4. The US FBI issued a May 13, 2025 alert about scammers impersonating immigration and university authorities and demanding student payments. This directly corroborates the specific transaction risk; it is not a rate of incidence among all international students. Source: https://www.fbi.gov/investigate/cyber/alerts/2025/impersonation-scheme-targeting-middle-eastern-students-in-the-united-states
5. Open Doors 2025 from IIE counts 1,177,766 international students in US higher education in 2024/25, including 8,104 originating from Indonesia. These are exposure-population counts, NOT counts of scammed students or paying customers. Sources: https://www.iie.org/news/open-doors-2025-press-release/ and https://opendoorsdata.org/wp-content/uploads/2025/11/OD25_Fast-Facts.pdf
6. **Indonesian real incident: Universitas Muhammadiyah Tapanuli Selatan (UMTS), Padangsidimpuan, February 2025.** The institution said approximately **273 students** were affected by alleged tuition-payment fraud, with a **reported financial discrepancy of about IDR 1.2 billion**. Two people posed as bank representatives offering easier fee payments. An investigation compared **28 payment slips with only six bank-recorded transactions**. These are incident-specific, initially investigated figures, not a national rate or evidence that every slip was forged. Subsequent court outcomes were reported in January 2026. Sources: https://www.detik.com/sumut/hukum-dan-kriminal/d-7791580/ada-273-korban-diduga-ditipu-2-mahasiwa-hingga-rp-1-2-m-di-sidimpuan and https://www.kompas.com/jawa-barat/read/2025/02/24/150000488/awal-mula-terbongkar-modus-penipuan-bayar-ukt-tanpa-ribet-273 and https://www.detik.com/sumut/hukum-dan-kriminal/d-8325227/2-penipu-rekan-sesama-mahasiswa-rp-1-2-m-di-sidimpuan-divonis-hingga-3-tahun-bui. This case is a **domestic analog of recipient impersonation and unverified payment evidence**, NOT itself a cross-border student payment.
7. **Singapore Police Force primary source, 19 March 2026:** at least 20 reported cases and at least S$31,000 in losses since March 2026 from emails impersonating educational institutions, directing students toward urgent external-bank payments. Source: https://www.police.gov.sg/Media-Hub/News/2026/03/20260319_police_advisory_on_resurgence_of_impersonation_scams_involving_educational_institutions. These are educational-institution impersonation cases; do not automatically label all victims international students.
8. ScamShield is a direct competitor for message/link scam screening and already has AI classification. Your hypothesis is that a **university policy-specific payment cross-check + evidence/status reconciliation + student-confirmed next action** provides incremental value beyond a generic scam classification. This is NOT independently proven. Primary source: https://www.scamshield.gov.sg/check-for-scams/how-to-check-for-scams-on-scamshield-app/.
9. Linguistic naming note: 保 (bǎo) has the established Chinese meaning of protection/guarding; CEKBAO is a coined mixed-language name. Do not present it as established Chinese vocabulary or link it to governmental endorsement. Dictionary: https://en.wiktionary.org/wiki/%E4%BF%9D.

10. World Bank's Remittance Prices Worldwide documents costs across transfer corridors. Its published global mean of 6.36% relates to remittances, **not to university tuition payments or live FX quotes**. Use published datasets only with dates and attribution. Source: https://remittanceprices.worldbank.org/

## Product positioning and bounds

- Primary user: international students preparing tuition/deposit transfers. Initial test context: students moving to a US university; localization for other countries is roadmap.
- Provisional institutional buyer: a university's international student office. This is a **hypothesis**, not a signed customer or proven willingness to pay.
- Clear JTBD: "Before sending an overseas tuition or rental deposit, help me establish whether the payment request follows a verified official process, understand the total cost, and prepare the next action if something is suspicious."
- Competition USP to test: **source-grounded pre-payment workflow with evidence links + cost disclosure + human-controlled safe next actions**, rather than generic scam classification or another money-transfer provider.
- Do not make guarantees like "fraud-free", "bank verified", "100% accurate", "loan approved" or "official university partner".

## Required MVP: one coherent, auditable financial decision workflow

Build a functional **pre-payment decision workflow** that is directly demonstrable. Generic "this looks like a scam" classification alone is not a sufficient feature. Keep the previous international-student scenario and add one Indonesian incident-inspired test, using invented institutions, accounts and receipts in all fixtures.

Critical correctness rule: **a visually believable receipt, bank statement screenshot or LLM interpretation cannot prove that funds reached an institution**. Only independent confirmation by the institution and/or payment provider can establish settlement. If no authorized source is available, output `PAYMENT_UNCONFIRMED` / `REQUIRES_INSTITUTION_CHECK` and create a safe verification request. Never assert "paid", "settled", "fraud confirmed" or "recipient verified" from documents alone.

## Required MVP: scenario workflows

**Scenario A — Suspicious international tuition request**
1. A student pastes an email requesting payment, the institution name, the amount, sender identity, stated beneficiary, country and deadline. Sanitize and extract structured fields with an LLM adapter when configured; otherwise fail transparently to a labeled deterministic demonstration mode.
2. Read a curated **sandbox trusted-channel registry**. Mark all fake institution data clearly as synthetic. When including any real institutions, manually verify their official domain and document the exact source URL, retrieval date and permitted payment channel. Never infer legitimacy from brand-like domains or email text alone.
3. Compare sender domain, beneficiary, payment method, deadline pressure and discount claims with the known trusted channel. Return statuses `MATCHED_SOURCE`, `CONFLICT`, and `NOT_VERIFIABLE`. **Do not equate `MATCHED_SOURCE` to a definitive bank-recipient authentication.**
4. For conflicts or missing ground truth: explicitly stop the proposed payment in sandbox; generate a safe-to-contact checklist and a draft email addressed to an independently verified official university contact. Do not auto-send. Show source URL(s) and precise mismatches.
5. Let the student provide two **illustrative** provider quotes (FX rate, flat fee, percent fee, expected recipient amount). Deterministically compare all-in cost and disclose reference date. Do not portray hypothetical figures as market quotes. Produce an auditable estimate and show unknown intermediary fees where applicable.
6. Require the authenticated student to explicitly approve creation of an **internal sandbox payment plan only**. Log proposal, approval, denial and subsequent edit. Never connect to live banks.
7. Export an evidence bundle (JSON plus downloadable HTML or PDF), containing sanitized request, source links, discrepancy findings, quote calculation, action recommendation, timestamps and audit event references.

**Scenario B — Domestic tuition-payment impersonation (inspired by the 2025 UMTS case)**
- Synthetic student receives an offer to pay tuition through an intermediary pretending to represent a bank and later receives an apparently legitimate payment slip.
- Build a transaction-evidence timeline containing the purported transfer, uploaded receipt metadata, the university ledger state as a **synthetic fixture**, and a bank-side recorded-payment state as a **synthetic fixture**.
- Mark `PAYMENT_UNCONFIRMED` or `CONFLICT` when the slip exists but the independent sandbox account ledger lacks a matching record; show the exact disagreement and advice to contact university finance through an independently obtained official channel.
- Test repeat slip identifiers, altered amounts, wrong destination, inconsistent dates and duplicate intermediary requests. Never imply a generic receipt-image detector alone can independently verify settlement.
- Explicitly state in the README/pitch that the **real UMTS event had domestic victims**. It supports the failure mechanism, while the competition solution targets both domestic and cross-border student finance workflows.

**Scenario C — Legitimate approved payment channel**
- Given a clearly labeled synthetic institution-approved request, compare the same inputs, create a pending payment plan only after confirmation, and export evidence. Mark recipient verification scope accurately.

**Scenario D — Incomplete or adversarial input**
- Unknown institution, manipulated university link, impossible FX quote, malicious instructions embedded in a pasted email, missing payee, and unauthorized approval attempt must fail closed, abstain or request clarification. Do not guess facts.

## Architecture and security

Prefer the smallest maintainable stack: Python 3.11+, FastAPI, SQLite, typed Pydantic models, Jinja2/vanilla JS or another equally small UI. Use Decimal for money. An OpenAI-compatible LLM tool-call adapter may be plugged in via environment variables (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`). The API key must never appear in logs or Git. Provide a deterministic demo mode for offline reviewers and label it clearly. Never claim offline parser tests constitute live-model evaluation.

Use a proper server-verified session identity. Roles/permissions must be enforced on the backend; never trust a role, account ID or approval flag sent in a client field. Enforce student-specific data scoping. Restrict URL retrieval to reviewed trusted domains and protect against SSRF, redirects to untrusted hosts, embedded prompt instructions, spoofed subdomains and malicious attachments. Do not browse arbitrary user-supplied payment links. Require bounded uploads or plain text, safe filenames, size limits, HTML escaping, and minimal PII retention. No production KYC, bank API, payment execution or visa/legal advice.

Keep `draft -> needs_review -> approved_or_blocked` states in a simple explicit workflow. Use idempotency keys for repeated approvals, audit logs with event IDs, typed tool arguments and deterministic permission checks. Model output must **never** directly authorize transactions or overwrite trusted-channel records.

## Acceptance tests, evidence and demo

Implement automated unit and integration tests covering:
- synthetic approved-channel match and conflicting payee;
- synthetic tuition-payment slip vs institution-ledger discrepancy, plus a matching synthetic confirmed ledger record;
- suspicious bank-agent impersonation and deadline-pressure detection;
- PDF/screenshot containing no independently authenticated settlement status must NOT yield "paid";
- unknown source returns `NOT_VERIFIABLE`;
- spoofed subdomain and malicious prompt injection are rejected;
- absent/expired session cannot approve;
- cross-user data access denied;
- duplicate request cannot execute the action twice;
- user rejection preserves state;
- quotes correctly compute all-in cost with `Decimal` and reject invalid/negative values;
- all outputs cite the exact source and label synthetic facts;
- model-offline fallback is clearly identified;
- evidence export is reproducible, contains no secrets and matches audit logs.

Provide at least four reproducible end-to-end scenarios with synthetic fixtures, including the UMTS-inspired receipt-ledger discrepancy. Execute actual test commands and preserve their exit codes, assertion counts and console outputs. Record a <=5-minute English-language screen-demo if video capture is available. If recording cannot run in this environment, create a detailed storyboard and mark video **NOT DONE**. Never fake test results or screen evidence. Distinguish code implemented, offline mocked evaluation and live LLM verification.

## Required project files

- `README.md`: current capabilities; honest limitations; setup; environment vars; reproducible run/test commands; evaluation scenarios; demo instructions.
- `.env.example`, `requirements.txt` or `pyproject.toml`, `LICENSE` with legitimately compatible third-party attribution.
- `app/`: backend, UI, trusted-source registry, financial calculations, authorization and audit services.
- `fixtures/`: synthetic student messages, approved channels and provider quotes clearly labeled.
- `tests/`: unit/integration/adversarial test cases.
- `docs/TECHNICAL.md`: architecture, core algorithm, financial calculation definitions, dataflow, permissions.
- `docs/SECURITY_SELF_ASSESSMENT.md`: threats, actual mitigations, remaining risks, scope.
- `docs/EXECUTION_EVIDENCE.md`: actual command outputs, reproducible scenario log, exact provenance.
- `docs/MARKET_EVIDENCE.md`: target problem, research limitations, verified domestic 273-student case and Singapore Police advisory, Flywire/ScamShield alternatives, specific differentiated hypothesis, channels and unvalidated market claims.
- `docs/PITCH_OUTLINE.md`: concise English 8–10-slide presenter-ready content, with claim/source discipline and no unverified feature claims.
- `docs/SUBMISSION_CHECKLIST.md`: exact official requirements and unfulfilled steps.

If possible, create a 10-minute presentation deck and optional evidence video after the functional core is verified. Do not sacrifice requirements 1, 4, 5 or 6 to build cosmetic features. Do not over-engineer multi-agent frameworks, vector databases, Kubernetes, wallets, or unnecessary infrastructure.


## Design-to-evidence gates (mandatory)

- **Market/problem evidence:** Use the Indonesian 273-student incident and the 2026 Singapore Police warning as named, dated cases. Never multiply either case into an incidence rate, TAM or expected revenue. Distinguish national context from international-student context.
- **Competitive differentiation:** Compare CEKBAO with Flywire, ScamShield, and existing university payment portals in one explicit matrix with grounded documented functions. Never claim to be the "first" or "only" without evidence. Brand is not the USP.
- **Proof of AI:** Include a real configurable LLM tool-calling loop for extracting entities and selecting approved read-only tools, with strict JSON-schema validation. If real provider credentials are not available, mark LLM NOT VERIFIED and run deterministic/offline tests. Do not invent model runs. Use a two-layer architecture where deterministic code owns policy, permissions, money calculations, and final status.
- **Comparison baseline:** In evaluation documentation, distinguish a rules-only baseline from any model-enabled run. Measure at least scenario completion, unsafe-action refusal, evidence attribution, and false-clearance errors on *synthetic fixtures*. Do not call these independent user studies.
- **Privacy/authorizations:** Never upload actual student IDs, phone numbers, passports, tuition slips or university access credentials to third-party models. No arbitrary URL fetch, no passwords, no OTPs, no live bank integrations, no production public service without permission.
- **Commit discipline:** Never run git commit, git push, git remote add, or create a GitHub repository. Prepare local diffs and copy-ready manual commands only.

## Execution order and reporting

1. Inspect workspace and competition documents. Make a short build plan, then immediately execute it.
2. Implement the end-to-end scenario and tests. Fix actual failures.
3. Run a local demo and document verification with exact commands.
4. Create supporting artifacts reflecting **actual** implementation status. Keep promised features out of 'implemented' sections.
5. Verify README installation from a clean environment if feasible.
6. Finish with a concise acceptance table: implemented/verified/blocked, and a list of changed files.
7. Leave all edits **uncommitted and unpushed**. State the exact manual `git add`, `git status`, `git diff --check`, `git commit`, and `git push` commands for the human to execute after review. Never invent a remote GitHub URL.

**Final constraint:** Deliver a working, traceable and secure sandbox prototype. It is better to have one end-to-end financial task that passes adversarial tests than several impressive but fake features.
