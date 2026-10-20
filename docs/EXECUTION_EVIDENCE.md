# CEKBAO execution evidence

This file records commands that were actually run, with their exit codes and outputs. All runs used synthetic data in a local sandbox. No live LLM, bank, payment provider or e-mail service was called.

## 1. Evidence classes

| Class | Meaning | Status |
|---|---|---|
| CODE IMPLEMENTED | Source code exists in `app/` | Yes |
| AUTOMATED TESTS | `pytest` run on this machine | 117 passed, exit code 0 |
| SANDBOX SCENARIO RUN | Real FastAPI app in-process, real HTTP routes, temporary SQLite | 18/18 expectations, exit code 0 |
| BASELINE EVALUATION | Synthetic labelled fixtures, keyword baseline vs CEKBAO rules-only | Exit code 0, results below |
| OFFLINE MOCKED LLM | Tool-calling loop against `httpx.MockTransport` | 13 tests passed |
| LIVE LLM VERIFICATION | A real model provider | **NOT DONE** (no credentials used) |
| MANUAL BROWSER CHECK | Local server on 127.0.0.1:8765, flows clicked in a browser pane | Done for Scenarios A, B, C (see section 6) |
| DEMO VIDEO | Screen recording of 5 minutes or less | **NOT DONE**. Storyboard in `docs/DEMO_STORYBOARD.md` |

## 2. Environment

- macOS 26.6.2 (Darwin 25.6.0), Python 3.11.15 in a virtual environment
- Packages pinned in `requirements.txt` and `requirements-dev.txt`
- Run date: 20 October 2026 (UTC timestamps in the logs)

## 3. Automated tests

Command:

```bash
.venv/bin/python -m pytest -v
```

Recorded output (head and tail of `evidence/pytest_output.txt`):

```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1, pluggy-1.7.0 -- /Users/ghazy/Ghazy/cekbao/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/ghazy/Ghazy/cekbao
configfile: pytest.ini
...
============================= 117 passed in 1.56s ==============================
PYTEST_EXIT_CODE=0
```

Test count per file: `test_api_security.py` 22, `test_export_and_e2e.py` 11, `test_llm_adapter.py` 13, `test_money.py` 18, `test_policy.py` 25, `test_settlement.py` 12, `test_urlguard.py` 16. Total 117.

### Mapping to the required acceptance tests

| Required test | Test name(s) |
|---|---|
| Synthetic approved-channel match and conflicting payee | `test_approved_channel_match_allows_plan_only_after_confirmation`, `test_conflicting_payee_blocks` |
| Slip vs institution-ledger discrepancy, plus a matching confirmed ledger record | `test_slip_without_ledger_record_is_unconfirmed_not_paid`, `test_matching_ledger_record_confirms`, `test_scenario_b_umts_inspired_receipt_ledger_discrepancy` |
| Bank-agent impersonation and deadline pressure | `test_bank_agent_impersonation_detected_and_conflicts_with_procedure`, `test_deadline_pressure_detected` |
| PDF or screenshot without authenticated settlement never yields "paid" | `test_pdf_receipt_claiming_paid_does_not_yield_paid`, `test_upload_metadata_never_changes_status` |
| Unknown source returns NOT_VERIFIABLE | `test_unknown_source_is_not_verifiable`, `test_no_fuzzy_institution_matching` |
| Spoofed subdomain and prompt injection rejected | `test_spoofed_and_manipulated_links_conflict`, `test_spoofed_sender_subdomain_conflicts`, `test_prompt_injection_cannot_clear_a_request`, `test_disallowed_tool_falls_back_and_cannot_approve` |
| Absent or expired session cannot approve | `test_no_session_cannot_read_or_approve`, `test_expired_session_cannot_approve`, `test_forged_session_cookie_rejected` |
| Cross-user access denied | `test_cross_user_access_denied`, `test_other_students_ledger_is_never_queried`, `test_reviewer_sees_only_escalated_cases_of_own_institution` |
| Duplicate request cannot execute twice | `test_duplicate_approval_executes_once`, `test_idempotency_key_reuse_with_different_body_rejected` |
| User rejection preserves state | `test_user_rejection_preserves_state` |
| Decimal all-in cost, invalid and negative values rejected | `test_all_in_cost_exact_decimal`, `test_float_precision_trap_is_avoided`, `test_parse_amount_rejects_invalid`, `test_negative_fee_rejected`, `test_impossible_rate_vs_reference_rejected` |
| Outputs cite the exact source and label synthetic facts | `test_outputs_cite_sources_and_label_synthetic` |
| Model-offline fallback clearly identified | `test_offline_mode_is_labeled`, `test_provider_error_falls_back` |
| Evidence export reproducible, no secrets, matches audit log | `test_export_is_reproducible_and_matches_audit_log`, `test_export_contains_no_secrets` |

## 4. Sandbox scenario run

Command:

```bash
.venv/bin/python scripts/run_scenarios.py
```

Exit code: 0. Full log (`evidence/scenario_run.log`):

```
CEKBAO scenario run started 2026-10-20T05:05:07+00:00 | extraction_mode=DETERMINISTIC_DEMO | registry 2026-10-20.1 sha256=0574b0361932dc0d...

== Scenario A: suspicious international tuition request (persona stu_ayu)
  case case_07cac55bfb05afe5: draft -> blocked | overall=CONFLICT decision=HOLD_DO_NOT_PAY
    INSTITUTION                      MATCHED_SOURCE  observed=Northbridge University
    SENDER_DOMAIN                    CONFLICT        observed=northbridge-university-payments.example
    LINK_DOMAIN                      CONFLICT        observed=https://pay.northbridge-university.example.secure-portal.example/confirm
    BENEFICIARY_NAME                 CONFLICT        observed=NBU International Collections Ltd
    BENEFICIARY_ACCOUNT              CONFLICT        observed=******9938
    SWIFT_BIC                        CONFLICT        observed=FKBKHKHHXXX
    PAYMENT_METHOD                   MATCHED_SOURCE  observed=international_wire, institution_portal
    AMOUNT                           NOT_VERIFIABLE  observed=USD 4850.00
    POLICY_NO_THIRD_PARTY_DISCOUNT   CONFLICT        observed=discount
    POLICY_NO_THREATS                CONFLICT        observed=visa status will be cancelled
    RISK DEADLINE_PRESSURE (warning): "URGENT; within 24 hours; today"
    RISK DISCOUNT_OFFER (high): "discount"
    RISK THREAT_OR_AUTHORITY_PRESSURE (high): "visa status will be cancelled"
    RISK OFF_CHANNEL_CONTACT (warning): "WhatsApp"
  [PASS] A.status: CONFLICT / HOLD_DO_NOT_PAY
  [PASS] A.plan_refused: propose plan -> HTTP 409 payment hold: the policy decision does not allow a payment plan
  [PASS] A.escalation_to_registry_contact: draft to student-accounts@northbridge-university.example auto_send=False
  evidence: scenarios/A_suspicious_international_request.evidence.json sha256=0177e3a1d6726e5c... events=5 chain_valid=True

== Scenario B: bank-agent offer + payment slips, UMTS-inspired (persona stu_budi)
  upload receipt for TRX-SYN-0002 -> HTTP 201 content_stored=False
  case case_e69ec73d6264fdf7: draft -> blocked | slips=3 confirmed=1 unconfirmed=1 conflict=1
    slip TRX-SYN-0001: CONFIRMED_BY_INSTITUTION_LEDGER next=KEEP_INSTITUTION_RECEIPT issues=[]
    slip TRX-SYN-0002: PAYMENT_UNCONFIRMED next=REQUIRES_INSTITUTION_CHECK issues=[]
    slip TRX-SYN-0004: CONFLICT next=CONTACT_BANK_AND_INSTITUTION issues=['WRONG_DESTINATION']
  [PASS] B.slip_statuses: {"TRX-SYN-0001": "CONFIRMED_BY_INSTITUTION_LEDGER", "TRX-SYN-0002": "PAYMENT_UNCONFIRMED", "TRX-SYN-0004": "CONFLICT"}
  [PASS] B.receipt_pdf_not_proof: PDF that says LUNAS/PAYMENT SUCCESSFUL stays PAYMENT_UNCONFIRMED
  [PASS] B.bank_agent_detected: BANK_AGENT_IMPERSONATION, DEADLINE_PRESSURE, DISCOUNT_OFFER, EASY_PAYMENT_OFFER, OFF_CHANNEL_CONTACT
  evidence: scenarios/B_umts_inspired_slip_ledger.evidence.json sha256=3265e19e6f2dd27c... events=5 chain_valid=True

== Scenario C: request through the approved channel (persona stu_citra)
  case case_f89fad45883ee04b: draft -> needs_review | overall=MATCHED_SOURCE decision=PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION
  [PASS] C.status: MATCHED_SOURCE / needs_review
    quote Provider A (illustrative): total IDR 8316125.00 all-in 16632.250000 markup 2.04% intermediary UNKNOWN
    quote Provider B (illustrative): total IDR 8255000.00 all-in 16510.000000 markup 1.29% intermediary KNOWN: 0.00
  [PASS] C.quote_choice: lowest=Provider B (illustrative) saves IDR 61125.00
  deny revision 1 -> HTTP 200 state=needs_review
  approve rev 2 -> HTTP 200 approved | replay same key -> HTTP 200 replay=True
  [PASS] C.approved_once: NOT_EXECUTED. Sandbox plan only. No money moved.
  evidence: scenarios/C_legitimate_approved_plan.evidence.json sha256=599f218d329445ea... events=9 chain_valid=True
  [PASS] C.audit_sequence: CASE_CREATED > EXTRACTION_COMPLETED > ANALYSIS_COMPLETED > ESCALATION_DRAFTED > QUOTES_COMPARED > PLAN_PROPOSED > PLAN_DENIED > PLAN_EDITED > PLAN_APPROVED

== Scenario D: incomplete and adversarial inputs (persona stu_ayu)
  D1_UNKNOWN_INSTITUTION: NOT_VERIFIABLE / HOLD_DO_NOT_PAY / state blocked | reasons: INSTITUTION: NOT_VERIFIABLE; SENDER_DOMAIN: NOT_VERIFIABLE; BENEFICIARY_NAME: NOT_VERIFIABLE; BENEFICIARY_ACCOUNT: NOT_VERIFIABLE
  [PASS] D.D1_UNKNOWN_INSTITUTION: fail closed
  D2_PROMPT_INJECTION: MATCHED_SOURCE / HOLD_DO_NOT_PAY / state blocked | reasons: RISK PROMPT_INJECTION
  [PASS] D.D2_PROMPT_INJECTION: fail closed
  evidence: scenarios/D2_prompt_injection.evidence.json sha256=394a59964bbf1e6d... events=5 chain_valid=True
  D3_MANIPULATED_LINK: CONFLICT / HOLD_DO_NOT_PAY / state blocked | reasons: LINK_DOMAIN: CONFLICT
  [PASS] D.D3_MANIPULATED_LINK: fail closed
  D4_MISSING_PAYEE: NOT_VERIFIABLE / HOLD_DO_NOT_PAY / state blocked | reasons: BENEFICIARY_NAME: NOT_VERIFIABLE; BENEFICIARY_ACCOUNT: NOT_VERIFIABLE
  [PASS] D.D4_MISSING_PAYEE: fail closed
  [PASS] D.impossible_fx_quote: HTTP 422: Provider A (illustrative): fx_rate deviates 99.99% from the reference rate (limit 25%). Th
  [PASS] D.reviewer_cannot_approve: HTTP 403
  [PASS] D.other_student_cannot_approve: HTTP 404
  [PASS] D.anonymous_cannot_approve: HTTP 401

SUMMARY: 18/18 expectations passed. Mode: DETERMINISTIC_DEMO (no live LLM call). Database: temporary file, discarded.
```

Artifacts: `evidence/scenario_summary.json` and eight files in `evidence/scenarios/` (JSON and HTML bundles for A, B, C and D2). Case IDs, event IDs and bundle hashes are random per run. Statuses and decisions are deterministic.

## 5. Baseline vs CEKBAO evaluation (synthetic fixtures)

Command:

```bash
.venv/bin/python scripts/evaluate.py
```

Exit code: 0. Output (`evidence/evaluate_console.txt`, full data in `evidence/evaluation.json`):

```
case                      label   keyword baseline  CEKBAO decision                           plan refused
A_SUSPICIOUS_INTL         unsafe  FLAG              HOLD_DO_NOT_PAY                           True
C_LEGITIMATE              safe    CLEAR             PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION   False
D1_UNKNOWN_INSTITUTION    unsafe  CLEAR             HOLD_DO_NOT_PAY                           True
D2_PROMPT_INJECTION       unsafe  CLEAR             HOLD_DO_NOT_PAY                           True
D3_MANIPULATED_LINK       unsafe  CLEAR             HOLD_DO_NOT_PAY                           True
D4_MISSING_PAYEE          unsafe  CLEAR             HOLD_DO_NOT_PAY                           True
E7_POLITE_LOOKALIKE       unsafe  CLEAR             HOLD_DO_NOT_PAY                           True
E8_LEGIT_WITH_URGENCY     safe    FLAG              PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION   False
E9_BANK_AGENT_OFFER       unsafe  FLAG              HOLD_DO_NOT_PAY                           True
E10_POLITE_ID_LOOKALIKE   unsafe  CLEAR             HOLD_DO_NOT_PAY                           True

slip            record exists  baseline accepts  CEKBAO status
TRX-SYN-0001    True           True              CONFIRMED_BY_INSTITUTION_LEDGER
TRX-SYN-0002    False          True              PAYMENT_UNCONFIRMED
TRX-SYN-0004    False          False             CONFLICT
TRX-SYN-0003    False          True              CONFLICT
TRX-SYN-0005    False          True              CONFLICT
TRX-SYN-0007    False          True              PAYMENT_UNCONFIRMED

METRICS (synthetic fixtures only, not a user study):
{
  "KEYWORD_BASELINE": {
    "scenario_completion": "not applicable (labels only, no workflow)",
    "unsafe_action_refusal": "not applicable (no action gate)",
    "unsafe_messages_flagged": "2/8",
    "false_clearance_messages": 6,
    "false_alarm_on_safe": 1,
    "false_clearance_slips": 4,
    "evidence_attribution": "0 (no sources cited)"
  },
  "CEKBAO_RULES_ONLY": {
    "scenario_completion": "10/10",
    "unsafe_action_refusal": "8/8",
    "unsafe_messages_flagged": "8/8",
    "false_clearance_messages": 0,
    "false_alarm_on_safe": 0,
    "false_clearance_slips": 0,
    "evidence_attribution": "63/70 findings cite a source URL with a synthetic label"
  },
  "MODEL_ENABLED": "NOT RUN: no LLM credentials configured. The adapter is tested only with a mock transport."
}
```

How to read this:

- The **keyword baseline** stands for generic scam-text screening. For slips it accepts any slip that looks complete and names an official-looking account. It has no action gate and cites no source.
- **CEKBAO rules-only** is the full app in DETERMINISTIC_DEMO mode.
- **Model-enabled** was not run. No credentials were configured. No live-model claim is made.
- 7 of 70 findings have no source URL. They belong to the unknown-institution case (D1), where no registry source exists. This is the intended behavior.
- **Limitation:** the same team wrote the fixtures and the rules. These numbers show that the rules do what they were designed to do on 10 messages and 6 slips. They do not measure real-world accuracy. They are not a user study.

## 6. Manual browser check

The server was started with:

```bash
CEKBAO_DB_PATH=data/demo.sqlite3 .venv/bin/python -m uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8765
```

Checked by clicking in a browser (20 October 2026):

| Flow | Observed |
|---|---|
| Sign-in with persona cards | Ayu, Citra and Budi signed in. Wrong persona tabs are hidden by role |
| Scenario A sample | Red verdict "Stop. Do not pay through this request.", 7 mismatches, registry contact, copyable draft, grouped checks, warning chips, plan locked |
| Scenario C sample | Green verdict, two quote cards (IDR 8,316,125.00 vs IDR 8,255,000.00, "Lowest total cost" badge on Provider B), plan prepared and approved, "Approved by you · not executed" |
| Scenario B sample | "1 of 3 payments confirmed by the university record", three-step timeline per slip (slip, bank, university record), next action per slip |
| Light and dark color schemes | Both readable |
| Console | Only the expected 401 from the session probe before sign-in |

## 7. Provenance

- The code, fixtures, tests and documents in this repository were written on 20 October 2026 by Team HMIF with an AI coding assistant (Claude Code). The team must review them before submission.
- The folder `CEKBAO_FinTechathon_2026_DRAFT_Package/` holds an earlier offline baseline from the same day (stdlib checker, 10 unit tests, 4 fixtures). This build supersedes it. It is not a prior MVP.
- No earlier ChatKas material is reused or presented as CEKBAO work.
