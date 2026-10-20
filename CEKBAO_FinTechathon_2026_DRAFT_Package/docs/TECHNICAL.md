# CEKBAO | Technical documentation

Status: PARTIAL OFFLINE BASELINE. Version: 2026-10-20. Team: HMIF. Track: C, Cross-border & Student Finance Assistant.

## 1. Purpose and limits
CEKBAO aims to help a student review suspicious tuition requests before attempting payment. It compares a request against a separately maintained institution policy. It can also reconcile a claimed receipt with an independent ledger. A match to a SYNTHETIC policy or ledger does NOT mean that real funds settled.

The attached runnable implementation is a DETERMINISTIC OFFLINE BASELINE, not a functional LLM agent, not a deployed student service, and not integrated with any university, payment provider, or bank. A source-linked student-facing model agent, authentication, and protected audit storage remain TO IMPLEMENT.

## 2. Problem evidence
Singapore Police Force (19 March 2026) reported at least 20 education-institution impersonation scam cases and at least S$31,000 in losses since March 2026. The warning mentions urgent tuition-transfer emails, compromised student accounts, and similar-looking institutional domains. Source: https://www.police.gov.sg/Media-Hub/News/2026/03/20260319_police_advisory_on_resurgence_of_impersonation_scams_involving_educational_institutions

UMTS / Padangsidimpuan (February 2025) had about 273 alleged victims according to initial university information. Initial reporting described a roughly IDR 1.2 billion discrepancy; a January 2026 court report cites a smaller IDR 231,562,500 audit loss for the institution. These are different measurements and must not be presented as identical. Source 1: https://www.detik.com/sumut/hukum-dan-kriminal/d-7791580/ada-273-korban-diduga-ditipu-2-mahasiwa-hingga-rp-1-2-m-di-sidimpuan Source 2: https://www.detik.com/sumut/hukum-dan-kriminal/d-8325227/2-penipu-rekan-sesama-mahasiswa-rp-1-2-m-di-sidimpuan-divonis-hingga-3-tahun-bui

## 3. User workflow (TARGET, not all implemented)
Input message or payment request -> structured fields -> official institution policy lookup -> mismatch detection -> optional receipt-ledger reconciliation -> evidence-backed status -> student confirms an internal plan or initiates external official contact. The final payment is always conducted outside CEKBAO on an independently accessed official service.

## 4. Implemented offline reference baseline
Code: sandbox/checker.py, sandbox/fixtures.json, sandbox/run_demo.py, sandbox/tests.py.

The baseline accepts a JSON fixture with institution code, request_url, payee, payment channel, optional pressure flag, optional slip ID, and optional synthetic ledger. It compares exact HTTPS hostname to one of two fictional institution domains. It compares requested recipient and channel to corresponding hardcoded fictional policy. If a receipt ID is present, it checks for a matching value in a purely SYNTHETIC ledger.

Three statuses exist: REQUIRES_OFFICIAL_CHECK, NOT_VERIFIABLE, and MATCHES_SYNTHETIC_POLICY_ONLY. None means BANK_VERIFIED, PAYMENT_SUCCESS, or SETTLED. Output contains exact check flags, policy source identifier, next action, and synthetic marker. No arbitrary remote URL is requested.

## 5. Planned AI-enabled architecture (NOT IMPLEMENTED)
User message -> authenticated API -> constrained extraction with an externally configured LLM -> validated data model -> deterministic policy engine -> read-only policy database -> deterministic comparison -> student-facing explanation with citations. The LLM shall not authorize payments, approve requests, or change policy records. A role-validated approval may only create an internal sandbox payment plan. Implement structured-output validation and fail-closed states.

Target technology: Python/FastAPI, SQLite, validated typed request models, short-lived server sessions, secure audit events, allowlisted policy sources and optional OpenAI-compatible LLM client. This target is NOT a description of the current baseline.

## 6. Financial operations and controls
The current baseline executes NO money transfer, foreign-exchange transaction, loan, lending decision, payout or settlement reconciliation. An optional future FX comparison must use Decimal values and clearly labeled user-supplied quotes. No FX provider rates were validated in this sandbox.

Planned role scope: student may create and review their own request; reviewer may review a synthetic institution policy; owner/admin may approve updates to that policy. All roles require server-verified identity. The baseline has no login, no multi-user database, no policy editing endpoint, and no permission-tier enforcement.

## 7. Reproducibility
From the extracted project folder:

cd sandbox
python run_demo.py
python -m unittest -v tests

Both commands use Python standard library and no external credentials. Output files: sandbox/execution_results.json and sandbox/execution_stdout.txt and unittest_results.txt. This is evidence for the offline deterministic reference baseline only.

## 8. Open gaps before official submission
Implement a true AI agent with tested provider or explicitly state not verified. Add backend authentication, session expiry, object-level access controls, constrained source registry, persistent immutable audit, typed tool execution, replay defenses, full end-to-end UI, reproducible clean-environment install, valid GitHub URL, and an actual <5-minute English demo-video recording. Update this document and the security report after running the agent and all security tests.

## 9. Source and version controls
Official rules: https://www.pol.cmu.ac.th/public/blog/attachment/download/7a51866a-4cee-42b5-9187-fa4e1f4df411
IEEE announcement: https://www.ieee-cis-singapore.org/2026-fintechathon
This document contains planned features and baseline findings, NOT independent efficacy, a live production deployment, institutional partnership, or acceptance by judges.
