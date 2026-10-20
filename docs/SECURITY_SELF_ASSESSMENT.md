# CEKBAO security self-assessment

Assessment date: 20 October 2026. Scope: the code in this repository (`app/`, `fixtures/`, `scripts/`) running locally as a sandbox. Assessor: Team HMIF, with AI coding assistance. This is a self-assessment, not an external audit or a certification.

The official checklist asks for "permission-tier implementation and known-risk list". Section 2 covers the tiers. Section 5 is the known-risk list.

## 1. Assets and trust boundaries

| Asset | Why it matters |
|---|---|
| Payment decision (`HOLD_DO_NOT_PAY` or plan allowed) | A false clearance can send tuition to a fraudster |
| Trusted-channel registry | If an attacker edits it, look-alike payees would match |
| Student case data | Messages and slips can contain personal and financial data |
| Sandbox payment plan and approval | Approval must come only from the owner, once, for the reviewed plan |
| Audit log and evidence bundle | The finance office relies on them to act |
| LLM API key (if configured) | Paid access, must not leak |

Trust boundaries: browser to API; API to the optional LLM provider; pasted message to every component (always untrusted); fixtures to the app (reviewed files, read-only at runtime).

## 2. Permission tiers (implemented and tested)

| Tier | How the server identifies it | Allowed | Denied |
|---|---|---|---|
| Anonymous | No valid session cookie | Health, registry list, synthetic samples, sign-in page | Every case route (HTTP 401) |
| `student` | Server-side session row joined to the user table | Create own cases. Analyze, quote, propose, edit, deny, approve, upload, export **own** cases only | Other students' cases (404, existence hidden). Office inbox (403). Approval of a blocked case (409) |
| `office_reviewer` | Same session mechanism, role from the user table | Read-only list and detail of **escalated** cases of its own institution. Student identities and raw messages are hidden. Intermediary contacts are hashed | Creating cases, approving or denying plans, uploads (403). Non-escalated cases (404) |
| System (code) | Not a login | Writes audit events such as `PAYMENT_HOLD` and `ESCALATION_DRAFTED` | Changing the registry. No route exists |
| LLM (optional) | Not a principal | Calls `lookup_institution` (read-only) and `submit_extraction` | Any other tool. Any status, role or approval. Raw PII never reaches it |

Role, owner, approval and status values never come from the client. Request models use `extra="forbid"`, so a body with `role`, `owner_id`, `approved` or `status` fails with HTTP 422.

Tests: `tests/test_api_security.py` (22 tests) and `tests/test_export_and_e2e.py` cover each row.

## 3. Threats and implemented mitigations

| # | Threat | Mitigation in code | Test evidence |
|---|---|---|---|
| T1 | Look-alike sender or link (`northbridge-university-payments.example`, `official.example.attacker.example`, `official@evil`, punycode, raw IP, HTTP, odd port) | Exact domain or label-boundary subdomain match. User-info, IP, punycode, non-ASCII, HTTP and non-443 ports conflict | `test_policy.py::test_spoofed_and_manipulated_links_conflict` (7 cases), `test_spoofed_sender_subdomain_conflicts`, `test_homoglyph_link_after_nfkc_is_rejected` |
| T2 | Prompt injection in the pasted message | Text stays data. Injection phrases raise a high signal that forces `HOLD_DO_NOT_PAY`. The LLM gets delimiters and a rule set. The deterministic layer decides | `test_prompt_injection_cannot_clear_a_request`, Scenario D2, `test_disallowed_tool_falls_back_and_cannot_approve` |
| T3 | Model hallucination or schema abuse | Strict JSON schema, Pydantic strict mode, enum and pattern checks, grounding against the source text, fallback | `test_llm_adapter.py` (13 tests, mock transport) |
| T4 | False settlement from a forged slip or a "LUNAS / PAID" PDF | Only an institution ledger record can confirm. Upload content is never parsed for status | `test_pdf_receipt_claiming_paid_does_not_yield_paid`, `test_slip_without_ledger_record_is_unconfirmed_not_paid` |
| T5 | Unauthorized approval or role spoofing | Server-side session, role check, owner check, `extra="forbid"` | `test_reviewer_cannot_approve_or_create`, `test_cross_user_access_denied`, `test_client_cannot_inject_role_owner_or_approval_fields` |
| T6 | Missing or expired session | Random 256-bit token, stored as SHA-256, 30-minute TTL, expired rows deleted | `test_no_session_cannot_read_or_approve`, `test_expired_session_cannot_approve`, `test_forged_session_cookie_rejected` |
| T7 | Cross-site request forgery | `SameSite=Strict` HttpOnly cookie plus per-session `X-CSRF-Token` header, compared in constant time | `test_missing_csrf_token_rejected` |
| T8 | Double execution of an approval | `Idempotency-Key` header required. Same key and body replays the stored response. Other key on an approved plan gives 409. A unique index allows one approved plan per case. Approval binds to plan revision and SHA-256 digest | `test_duplicate_approval_executes_once`, `test_idempotency_key_reuse_with_different_body_rejected`, `test_stale_plan_digest_rejected` |
| T9 | Cross-user data access through ledger lookup | Ledger and bank-feed lookups use the signed-in user's payer reference. A slip with another reference triggers no lookup | `test_other_students_ledger_is_never_queried`, `test_ledger_tool_is_scoped_by_payer` |
| T10 | Malicious upload | Allowlist (pdf, png, jpg, txt), magic-byte check, 1 MB limit, PDF active-content scan (`/JavaScript`, `/JS`, `/Launch`, `/EmbeddedFile`, `/RichMedia`, `/XFA`), double-extension block, path stripping. Content discarded after hashing | `test_malicious_uploads_rejected` (7 cases) |
| T11 | SSRF through link fetching | The analysis never fetches links. `safe_fetch` (maintenance only) allows HTTPS hosts on the reviewed allowlist, rejects private and link-local IPs, checks every redirect hop, caps size | `test_urlguard.py` (16 tests) |
| T12 | Stored XSS through message content | Jinja autoescape. The UI renders data with `textContent`. CSP `script-src 'self'` with no inline scripts. Evidence HTML has `default-src 'none'` and no scripts | `test_html_export_escapes_hostile_content`, `test_security_headers_and_cookie_flags` |
| T13 | Registry tampering through the app | No write route. Frozen Pydantic models, deep copies on read. SHA-256 recorded per analysis. Non-synthetic entries need an https source and a reviewer | `test_registry_is_read_only_copy`, `test_registry_rejects_real_entry_without_provenance` |
| T14 | Secret or PII leakage | Redaction before any model call. Masked accounts and phones. API key with `repr=False`, never logged. Validation errors do not echo input. Idempotency keys stored as hashes in audit | `test_model_sees_only_redacted_text`, `test_api_key_never_leaks`, `test_export_contains_no_secrets`, `test_validation_errors_do_not_echo_input` |
| T15 | Brute force on sign-in | 5 failures in 15 minutes lock the user. PBKDF2-SHA256 hashes. Constant-time compare | `test_wrong_access_code_and_lockout` |
| T16 | Oversized input | 2 MB request limit, 20,000-character message limit, bounded lists (30 slips, 3 quotes, 20 links) | `test_oversized_request_rejected`, `test_message_length_limit_fails_closed` |
| T17 | Audit tampering | Per-case SHA-256 hash chain with `prev_hash`. Exports report `audit_chain_valid`. Exports are logged outside the chain | `test_export_is_reproducible_and_matches_audit_log` |

## 4. Compliance-oriented controls

- **No financial execution.** No route moves money or calls a bank. Plans carry `execution: NOT_EXECUTED`.
- **No advice beyond the procedure.** CEKBAO gives no visa, legal or investment advice.
- **Claim discipline.** The code never outputs "paid", "settled", "fraud confirmed", "recipient verified" or "bank verified". Test `FORBIDDEN_CLAIMS` checks system-authored text in the scenario tests.
- **Data minimization.** See `docs/TECHNICAL.md` section 5.
- **Synthetic data only.** No real student, account, institution or receipt is in the repository.

## 5. Known-risk list (remaining risks)

| ID | Risk | Severity | Why it remains | Next mitigation |
|---|---|---|---|---|
| R1 | Registry accuracy. A wrong or stale entry gives a wrong comparison | High | All entries are synthetic. There is no real update process | Institution-signed registry feed, source expiry dates, two-person review |
| R2 | Demo sign-in is not production identity | High | Access codes are sandbox test values in a fixture. No MFA, no SSO | University SSO (OIDC), MFA, disable `CEKBAO_DEMO_USERS` |
| R3 | Regex extractor coverage | Medium | Formats outside the samples can be missed | Fails closed to `NOT_VERIFIABLE`. Add a labelled test corpus and a validated LLM extractor |
| R4 | LLM not verified with a real provider | Medium | No credentials were used. Only the mock protocol is tested | Run a documented evaluation with a chosen model, compare with the rules-only baseline |
| R5 | Forged `From:` header with the real domain | Medium | No SPF, DKIM or DMARC check | Ask for the original headers or integrate a mail gateway verdict. CEKBAO already tells students to open the portal themselves |
| R6 | No encryption at rest and no retention purge | Medium | Local SQLite file | Encrypted storage, retention job (for example 30 days), deletion on request |
| R7 | Rate limits are in-process | Low | Single-process sandbox | Reverse proxy limits, shared store |
| R8 | DNS rebinding in `safe_fetch` | Low | Resolve-then-connect race. Not used by the analysis flow | Pin the resolved IP for the connection |
| R9 | Negation heuristic false signals | Low | 45-character window | Larger labelled corpus, sentence parser |
| R10 | Social engineering outside the app | Medium | A student can ignore the hold | Clear verdict UI, office escalation, user research |
| R11 | Dependency vulnerabilities | Low | Pinned versions, no automated scan yet | Add `pip-audit` to CI |
| R12 | Session in a shared browser | Low | 30-minute TTL, explicit sign-out | Shorter idle timeout for kiosks |

## 6. Not implemented (stated plainly)

Production deployment, HTTPS termination, external penetration test, privacy impact assessment, encryption at rest, retention automation, SSO, MFA, real institution data, real bank or provider integration, live LLM evaluation, independent user testing.
