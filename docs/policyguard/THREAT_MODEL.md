# Threat model: CEKBAO PolicyGuard

Assets: payment instructions (may contain personal data), institution policies and authority grants, decisions and evidence snapshots, reviewer actions, budget, credentials (Nebius key, signing keys, sessions).

| Threat | Control | Test | Residual risk |
|---|---|---|---|
| SQL injection | SQLAlchemy Core with bound parameters; the only dynamic SQL fragments are fixed strings | All integration tests run real queries; ruff/mypy on new code | Low |
| XSS | Jinja2 autoescape; no `|safe`; model output never rendered as HTML; CSP `script-src 'self'; style-src 'self'` from the existing app | `test_web.py` renders instruction text containing markup-like content as text | Low |
| CSRF | SameSite=Strict session cookie plus per-session CSRF token on every form and the upload endpoint | `test_web.py` uploads require `X-CSRF-Token`; sign-out checks the token | Low |
| IDOR / tenant leakage | Every query filters `tenant_id`; payers read only their own cases; same 404 for "missing" and "not yours"; cache keys include tenant | `test_11_*` (service and API), `test_snapshot_cache_is_tenant_scoped_and_epoch_keyed`, `test_other_tenant_cannot_complete_upload` | Medium: web tenancy is fixed to the demo tenant until an IdP supplies tenant claims |
| DDoS / abuse | Per-tenant token bucket (Redis Lua), 429 + Retry-After, request size limit (2 MB), upload limit (1.5 MB), bounded polling | `test_rate_limit_returns_429_with_retry_after_per_tenant`, `test_limiter_degrades_to_stricter_local_limit_when_redis_is_down` | Medium: no edge WAF or autoscaling plan applied |
| MitM | HTTPS is required in deployment (not applied); Nebius calls use HTTPS with redirects disabled; cookies can be marked Secure (`CEKBAO_COOKIE_SECURE=1`) | n/a locally | Open until deployed behind TLS |
| SSRF | Crawler not enabled; the existing `app/urlguard.safe_fetch` (allowlist, private-IP and redirect checks) is the only fetcher; instruction URLs are never fetched or linked | Existing `tests/test_urlguard.py` | Medium: approved-source ingestion with DNS pinning is not implemented in PolicyGuard yet |
| Prompt injection | Instruction sent as data in tags, fixed system prompt, strict schema, quote grounding, rules decide; injection patterns escalate a matching result to REQUIRES_REVIEW | `test_09_*` (rules and adapter) | Low for decisions; the model can still omit fields (shown as "Not found") |
| Memory poisoning | Experience records only from authorized reviewers, behind a flag, invalidated on revocation, not used for decisions | `test_19_*`, `test_06_*` | Low (feature unused) |
| Supply chain | Pinned Python and npm versions with lockfiles; npm versions match the existing `video/` lockfile; pip-audit and SBOM tooling installed | `pip-audit` / CycloneDX run: see `SECURITY_CHECKS.md` | Medium |
| Replay | Idempotency keys (unique per tenant), processed-events deduplication, signed upload URLs bound to upload ID and expiry, single-use upload slot | `test_12_*`, `test_13_*`, `test_tampered_or_expired_upload_url_is_refused` | Low |
| Credential leakage | Keys only from environment or git-ignored `.env.local`; `repr=False`; never logged; demo-video manifest refuses secret-like keys and values; Lighthouse reports scrub the session cookie | `tools/demo-video` test "secrets are refused" | Low |
| Unauthorized policy change | Approve/revoke need `policy_admin` with MFA (`amr`), the discoverer cannot approve, optimistic concurrency, hash-chained audit | `test_policy_approval_needs_admin_mfa_and_a_second_person`, `test_policy_approval_requires_mfa` | Medium: web sessions have no MFA, so policy changes are API-only |
| Over-claiming | Transaction status always UNKNOWN; "safe to pay" never shown; preview videos labelled MOCK | `test_rules_never_claim_settlement` (property test), `test_result_reading_order_and_no_safety_claim` | Low |
