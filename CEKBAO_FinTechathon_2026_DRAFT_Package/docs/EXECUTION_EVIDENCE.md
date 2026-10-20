# CEKBAO | Execution evidence and limitations

Captured: 2026-10-20 04:36 UTC. Evidence class: DETERMINISTIC SYNTHETIC BASELINE, NOT live LLM agent.

## 1. Commands actually executed
cd sandbox
PYTHONDONTWRITEBYTECODE=1 python run_demo.py
PYTHONDONTWRITEBYTECODE=1 python -m unittest -v tests

Both commands exited with status 0 in the local runtime. Python version and dependencies are recorded in the README. No network/API/provider calls were used.

## 2. Four sandbox scenarios (actual stdout)
INTL-IMP-01 status=REQUIRES_OFFICIAL_CHECK flags=REQUEST_DOMAIN_MISMATCH,PAYEE_MISMATCH,PAYMENT_CHANNEL_MISMATCH,URGENCY_PRESSURE verified_settlement=False
ID-SLIP-01 status=REQUIRES_OFFICIAL_CHECK flags=SLIP_NOT_FOUND_IN_SYNTHETIC_LEDGER verified_settlement=False
LEGIT-01 status=MATCHES_SYNTHETIC_POLICY_ONLY flags=none verified_settlement=False
UNKNOWN-01 status=NOT_VERIFIABLE flags=UNKNOWN_INSTITUTION verified_settlement=False
4/4 synthetic scenario outcomes matched expected statuses.

All four inputs and expected outcomes are included in sandbox/fixtures.json and sandbox/run_demo.py. Scenario 1 flags forged institutional host and payee. Scenario 2 uses a fictitious ledger inspired by the UMTS failure mechanism. Scenario 3 matches a fictionally approved channel but does NOT establish bank settlement. Scenario 4 refuses an unknown institution. All are artificial test cases, not observed students.

## 3. Actual unit test output
test_domain_mismatch_flags (tests.BaselineTests.test_domain_mismatch_flags) ... ok
test_http_not_accepted (tests.BaselineTests.test_http_not_accepted) ... ok
test_ledger_disagreement (tests.BaselineTests.test_ledger_disagreement) ... ok
test_missing_slip_in_synthetic_ledger (tests.BaselineTests.test_missing_slip_in_synthetic_ledger) ... ok
test_no_spoof_subdomain (tests.BaselineTests.test_no_spoof_subdomain) ... ok
test_payee_mismatch (tests.BaselineTests.test_payee_mismatch) ... ok
test_policy_match_not_settlement (tests.BaselineTests.test_policy_match_not_settlement) ... ok
test_spoof_domain (tests.BaselineTests.test_spoof_domain) ... ok
test_unknown_fails_closed (tests.BaselineTests.test_unknown_fails_closed) ... ok
test_urgency_flag (tests.BaselineTests.test_urgency_flag) ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.000s

OK

## 4. Artifacts and reproducibility
sandbox/execution_results.json contains the exact four output records. sandbox/execution_stdout.txt and sandbox/unittest_results.txt preserve terminal outputs. Run the two documented Python commands to reproduce them.

## 5. Evidence NOT currently available
NOT VERIFIED: actual AI model inference or real LLM provider integration, tested agent tool calls, authenticated sessions, permission-tier implementation, sandbox action approval, live university policies, trusted bank settlement, payment provider FX quotes, recorded browser UI, student interviews, user effectiveness, hosted website or a public GitHub repository.

NOT RECORDED: demo video. A recording script exists, but a storyboard is not video evidence. The official non-on-chain execution-evidence checklist calls for sandbox logs AND demo video. Do not submit a storyboard as if it were that video.

## 6. Completion guidance
Run the agentic CEKBAO MVP implementation prompt to build the actual user-facing agent, secure app and tests. Regenerate all documentation and this evidence from verified implementation. Record the screen demo with actual interactions and review credentials securely. The README and current slides clearly label this reference as a deterministic baseline.
