# CEKBAO | Student Payment Verification Agent

**Check the request. Use the official payment route.** 学费支付核验助手 (descriptive subtitle: tuition payment cross-check assistant)

Team HMIF (Ghazy Achmed Movlech Urbayani, M Azzam Robbani). 2026 Shenzhen International FinTech Competition (FinTechathon), International Track, Topic C: Cross-border & Student Finance Assistant.

CEKBAO helps a student check a tuition or deposit payment request **before** any money moves. It compares the sender, payee, payment channel and payment evidence with a curated, documented university payment procedure. It holds the payment when something does not match, drafts a message to the official finance office and exports an auditable evidence record. Deterministic code decides every status and every permission. An optional language model only helps to read the message.

> **Status: working sandbox prototype.** All institutions, accounts, ledgers, bank feeds and quotes are **synthetic**. CEKBAO moves no money, connects to no bank, sends no e-mail and does not authenticate a payee against a bank registry.

The name CEKBAO is an original bilingual coinage: Indonesian *cek* (check) + Mandarin 保 *bǎo* (protect). It is not an established Chinese word, and the team has not done a trademark clearance.

---

## 1. What works today

| Capability | Status | Where |
|---|---|---|
| Paste a payment request (e-mail or chat), sanitize it and extract fields | Implemented, tested | `app/sanitize.py`, `app/extractor.py` |
| Compare sender domain, links, payee, account, SWIFT, method and procedure rules with a read-only registry | Implemented, tested | `app/policy.py`, `app/registry.py`, `fixtures/registry.json` |
| Statuses `MATCHED_SOURCE`, `CONFLICT`, `NOT_VERIFIABLE` and the gate `HOLD_DO_NOT_PAY` | Implemented, tested | `app/models.py`, `app/policy.py` |
| Risk signals: deadline pressure, discounts, threats, bank-agent claims, OTP requests, chat-app contacts, prompt injection, hidden characters, repeated intermediary | Implemented, tested | `app/policy.py` |
| Safe-to-contact checklist and a draft e-mail to the **registry** contact (never auto-sent) | Implemented, tested | `app/escalation.py` |
| Slip vs bank feed vs institution ledger reconciliation (`PAYMENT_UNCONFIRMED`, `REQUIRES_INSTITUTION_CHECK`, `CONFLICT`) | Implemented, tested | `app/settlement.py` |
| Two or three user-provided FX quotes, all-in cost with `Decimal`, unknown intermediary fees disclosed | Implemented, tested | `app/money.py` |
| Sandbox payment plan: propose, edit, deny, approve with idempotency key and plan digest | Implemented, tested | `app/workflow.py` |
| Server-side sessions, CSRF, roles (`student`, `office_reviewer`), owner-scoped access | Implemented, tested | `app/auth.py`, `app/workflow.py` |
| Hash-chained audit log and reproducible JSON/HTML evidence export | Implemented, tested | `app/audit.py`, `app/export.py` |
| Bounded receipt upload (metadata and SHA-256 only, type and active-content checks) | Implemented, tested | `app/uploads.py` |
| Allowlist-only fetch guard (SSRF, redirects, private IPs, size) | Implemented, tested (not used by the analysis flow) | `app/urlguard.py` |
| OpenAI-compatible tool-calling extractor with strict schema, grounding and fallback | Implemented, tested with a **mock** transport only. **LLM NOT VERIFIED** with a live provider | `app/llm.py` |
| Web UI: verdict first, next steps, checks, warnings, costs, plan, slip timeline, office inbox | Implemented, manually checked in a browser | `app/templates/`, `app/static/` |
| Demo video | **NOT DONE** (storyboard only) | `docs/DEMO_STORYBOARD.md` |

## 2. Honest limitations

- The registry holds **zero real institutions**. Two synthetic universities use the reserved `.example` domain.
- `MATCHED_SOURCE` means "the field matches the curated registry entry". It is not bank-level payee authentication. A matching `From:` header can be forged.
- A slip, receipt or screenshot never proves settlement. Only a record from the institution can do that. Here, that record is a synthetic fixture.
- The deterministic extractor uses regular expressions. It handles the sample formats in English and Indonesian. Other formats can produce `NOT_VERIFIABLE`. It fails closed, never open.
- No live LLM was called. The tool-calling loop is tested only against a mock provider.
- Demo sign-in uses sandbox access codes. It is not production identity, KYC or MFA.
- The evaluation uses synthetic fixtures written by the same team that wrote the rules. It shows the rules behave as designed. It is not real-world accuracy and not a user study.
- No institution, provider or buyer has validated the product. The university-office buyer is a hypothesis.

## 3. Setup

Requirements: Python 3.11 or newer. No API key is needed.

```bash
python3.11 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements-dev.txt
```

## 4. Run the tests and the evidence scripts

```bash
.venv/bin/python -m pytest -v
```

```bash
.venv/bin/python scripts/run_scenarios.py
```

```bash
.venv/bin/python scripts/evaluate.py
```

The scenario script starts the real app in-process on a temporary SQLite database. It writes `evidence/scenario_run.log`, `evidence/scenario_summary.json` and one evidence bundle (JSON and HTML) per scenario into `evidence/scenarios/`. Exit code 0 means every expectation held.

## 5. Run the web app locally

```bash
.venv/bin/python -m uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765 and sign in with a demo persona. The access codes below are **sandbox test values** from `fixtures/demo_users.json`. They are not real credentials.

| Persona | Role | Demo access code | Try |
|---|---|---|---|
| Ayu | student (US-bound) | `demo-ayu-2026` | "Urgent deposit e-mail", "Hidden instructions", "Fake portal link" |
| Citra | student (US-bound) | `demo-citra-2026` | "Official invoice e-mail", then compare costs and approve a plan |
| Budi | student (Indonesia) | `demo-budi-2026` | Tab "Did my payment arrive?", sample "Bank-agent offer + 3 slips" |
| Finance office | office_reviewer | `demo-officer-2026` | Office inbox (escalated requests, read-only) |

## 6. Environment variables

Copy `.env.example` and export the values in your shell. Never commit a real `.env`.

| Variable | Default | Meaning |
|---|---|---|
| `CEKBAO_DB_PATH` | `data/cekbao.sqlite3` | SQLite file |
| `CEKBAO_SESSION_TTL_MINUTES` | `30` | Session lifetime |
| `CEKBAO_DEMO_USERS` | `1` | Seed the synthetic personas |
| `CEKBAO_COOKIE_SECURE` | `0` | Set `1` behind HTTPS |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | empty | Optional OpenAI-compatible endpoint. Empty means DETERMINISTIC DEMO MODE |

When the three LLM variables are set, CEKBAO sends **only redacted text** (e-mail addresses, phone numbers, account and ID numbers replaced by placeholders). Calling a paid API is your decision. The team did not run one.

## 7. Evaluation scenarios

| ID | Scenario | Expected result |
|---|---|---|
| A | Look-alike sender asks for an urgent deposit to a third-party account, threatens the visa, offers a discount | `CONFLICT`, `HOLD_DO_NOT_PAY`, draft to the registry contact |
| B | Indonesian "bank agent" offer plus three slips (UMTS-inspired, all data invented) | Slip 1 `CONFIRMED_BY_INSTITUTION_LEDGER`, slip 2 `PAYMENT_UNCONFIRMED`, slip 3 `CONFLICT` |
| C | Request through the approved channel | `MATCHED_SOURCE`, quotes compared, plan approved once, not executed |
| D1 | Unknown institution | `NOT_VERIFIABLE`, hold |
| D2 | Embedded prompt injection in an otherwise matching e-mail | `MATCHED_SOURCE` but `HOLD_DO_NOT_PAY` |
| D3 | Link with user-info trick (`official@evil`) | `CONFLICT`, hold |
| D4 | Missing payee | `NOT_VERIFIABLE`, hold |
| D5 | Impossible FX quote, negative fee | HTTP 422, logged |
| D6 | Approval by another student, the office reviewer, or no session | 404, 403, 401 |

Recorded results are in `docs/EXECUTION_EVIDENCE.md`.

## 8. Demo instructions (manual screen recording)

Follow `docs/DEMO_STORYBOARD.md`. It lists every click and the expected screen for a recording of 5 minutes or less. Record with macOS Screenshot (Shift-Command-5) or QuickTime. Record only the browser window.

## 9. Repository layout

```
app/            FastAPI app, policy engine, money, settlement, auth, audit, export, UI
fixtures/       Synthetic registry, personas, messages, ledger, bank feed, samples
tests/          117 unit, integration and adversarial tests
scripts/        run_scenarios.py, evaluate.py
evidence/       Recorded test output, scenario log, evaluation, evidence bundles
docs/           Technical, security, execution evidence, market, pitch, checklist, storyboard
CEKBAO_FinTechathon_2026_DRAFT_Package/   Earlier offline baseline and draft documents (superseded, kept for reference)
```

## 10. Documentation

- `docs/TECHNICAL.md`: architecture, algorithm, money definitions, data flow, permissions
- `docs/SECURITY_SELF_ASSESSMENT.md`: permission tiers, threats, mitigations, known risks
- `docs/EXECUTION_EVIDENCE.md`: commands, exit codes, outputs, provenance
- `docs/MARKET_EVIDENCE.md`: problem evidence, alternatives, hypothesis, unvalidated claims
- `docs/PITCH_OUTLINE.md`: 10-slide outline for a presentation of 10 minutes or less
- `docs/SUBMISSION_CHECKLIST.md`: official requirements and open steps
- `docs/DEMO_STORYBOARD.md`: demo recording script (video NOT DONE)
- `docs/screenshots/`: real screenshots of the running app (Scenarios A, B, C), taken on 20 October 2026

## 11. License and attribution

MIT for the CEKBAO source (see `LICENSE`). Third-party packages are listed in `THIRD_PARTY_NOTICES.md`. Fixtures contain only invented data. No real student, account or institution data is in this repository.
