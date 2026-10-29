# Requirement → code → test → evidence → status

Statuses: IMPLEMENTED (code exists, not verified by a test), VERIFIED_LOCAL (tests or measurements on this machine), VERIFIED_LIVE (verified against the real external service), BLOCKED (cannot proceed without an external input), NOT_DONE (not started in this iteration; listed so nothing is implied).

## Mandatory test cases from the brief

| # | Case | Code | Test | Status |
|---|---|---|---|---|
| 1 | Instruction matches the applicable policy | `domain/rules.py` | `test_rules.py::test_01_*` | VERIFIED_LOCAL |
| 2 | Account conflicts with policy | `domain/rules.py` | `test_rules.py::test_02_*`, `test_web.py::test_comparison_table_*` | VERIFIED_LOCAL |
| 3 | Evidence or validity date missing | `domain/rules.py` | `test_rules.py::test_03_*` | VERIFIED_LOCAL |
| 4 | Old policy right historically, wrong for a new payment | `domain/rules.py::assess_case` | `test_rules.py::test_04_*`, `test_intake_queue.py::test_04_*`, `test_web.py::test_policy_change_*` | VERIFIED_LOCAL |
| 5 | Two authoritative sources conflict | `domain/rules.py` | `test_rules.py::test_05_*`, `test_web.py::test_comparison_shows_both_conflicting_sources` | VERIFIED_LOCAL |
| 6 | Revocation invalidates cache and experience | `application/service.py::Policies`, `infra/pg.py::PolicySnapshots` | `test_06_*` (service, Redis) | VERIFIED_LOCAL |
| 7 | Policy changes while a worker processes | `Worker._commit` epoch check | `test_07_*` | VERIFIED_LOCAL |
| 8 | Model fabricates quotes or returns invalid JSON | `application/extraction.py::ground`, `infra/nebius.py` | `test_nebius_adapter.py::test_08_*` | VERIFIED_LOCAL (mock transport; not live) |
| 9 | Prompt injection in the document | rules escalation, adapter framing | `test_09_*` | VERIFIED_LOCAL |
| 10 | Crawler redirect to a private network | existing `app/urlguard.py::safe_fetch` | `tests/test_urlguard.py` | VERIFIED_LOCAL for the existing fetcher; PolicyGuard source ingestion NOT_DONE |
| 11 | Access to another tenant's case, object or cache | tenant filters, owner checks, tenant cache keys | `test_11_*` (service, API), cache and upload tests | VERIFIED_LOCAL |
| 12 | Concurrent idempotent requests | unique `(tenant_id, idempotency_key)` | `test_12_*` (8 threads) | VERIFIED_LOCAL |
| 13 | Duplicate or out-of-order events | `processed_events`, unique `jobs.source_event_id` | `test_13_*` | VERIFIED_LOCAL |
| 14 | Worker dies after commit, before acknowledgement | lease expiry, fencing | `test_14_*`, `test_lost_lease_cannot_commit` | VERIFIED_LOCAL |
| 15 | Provider 429, 5xx, timeout, partial response | adapter errors, retry with jitter, rules fallback | `test_15_*` (adapter and queue) | VERIFIED_LOCAL (mock transport) |
| 16 | Database, cache, queue or storage outage | 503 on storage failure, Redis fallback | `test_16_*`, limiter fallback test, `/readyz` | VERIFIED_LOCAL (storage outage for objects not simulated) |
| 17 | Budget exhausted while jobs wait or retry | `PgBudgetLedger` with CHECK constraints | `test_17_*` | VERIFIED_LOCAL |
| 18 | Upload too large or dangerous | `application/uploads.py` + `app/uploads.inspect_upload` | `test_18_*`, `test_upload_rejection_reason_is_returned` | VERIFIED_LOCAL |
| 19 | Unauthorized reviewer tries to change experience | role check before experience write | `test_19_*` | VERIFIED_LOCAL |
| 20 | Keyboard and screen reader complete the main flow | semantic SSR pages | keyboard run in `tools/ui-qa` (`audit-summary.json`) | Keyboard VERIFIED_LOCAL; screen reader NOT_DONE |

## Main requirements

| Requirement | Code | Test / evidence | Status |
|---|---|---|---|
| Three separate decision dimensions; never SETTLED from text | `domain/model.py`, `rules.py` | property test `test_rules_never_claim_settlement` | VERIFIED_LOCAL |
| Half-open intervals, bitemporal recorded time | `domain/temporal.py` | `test_temporal.py` (incl. Hypothesis) | VERIFIED_LOCAL |
| PolicyVersion metadata fields from the brief | `infra/tables.py::policy_versions`, migration `0001` | migration applied to two databases | VERIFIED_LOCAL |
| `POST /v1/cases` 202 / 409 / 503 / 429, OpenAPI | `api/v1.py` | `test_api_v1.py` | VERIFIED_LOCAL |
| Uploads with signed URL, quarantine, scan | `application/uploads.py`, `infra/storage.py` | `test_api_v1.py`, `test_storage.py` (moto S3) | VERIFIED_LOCAL |
| Reviews and policy approval with roles, MFA, optimistic concurrency | `application/service.py` | `test_intake_queue.py`, `test_api_v1.py` | VERIFIED_LOCAL |
| Outbox, queue states, lease, heartbeat, backoff, DLQ, audited replay | `infra/pg.py`, `service.py` | `test_intake_queue.py` | VERIFIED_LOCAL |
| Indexes and query plans on 100,000 cases | `tables.py` | `QUERY_PLANS.md` | VERIFIED_LOCAL |
| Token bucket per tenant, tenant-scoped cache with epoch | `infra/ratelimit.py`, `infra/cache.py` | `test_limiter_cache.py` (real Redis) | VERIFIED_LOCAL |
| NVIDIA model via Nebius in the main flow | `infra/nebius.py`, `runtime.py` | `scripts/nebius_live_check.py` | BLOCKED (no API key or budget); contract VERIFIED_LOCAL |
| OpenTelemetry traces, traceparent in events | `infra/telemetry.py`, outbox envelope | envelope test checks `traceparent` | IMPLEMENTED (no collector; export not verified) |
| OIDC with MFA for admins | `infra/auth.py` (JWT/JWKS, `amr`) | `test_api_v1.py` | VERIFIED_LOCAL with a local key; real IdP BLOCKED |
| SSR web, English UI, externalized strings | `policyguard/web/` | `test_web.py` (24 tests) | VERIFIED_LOCAL |
| WCAG 2.2 AA target, responsive 320–1440 | `static/*.css`, templates | axe 0 violations, 0 overflow, keyboard run, Lighthouse a11y 100 (lab) | VERIFIED_LOCAL (automated + keyboard); screen reader and user sessions NOT_DONE |
| Design system and DESIGN.md | `tokens.css`, `DESIGN.md`, `CONTRAST.md` | 38 contrast pairs measured | VERIFIED_LOCAL |
| Load profiles (20 rps baseline, 200 rps spike, soak) | — | — | NOT_DONE |
| Evaluation A (newest version) vs B (temporal) | `domain/temporal.py` selectors, `scripts/policyguard_eval.py` | `EVALUATION.md`: A 15/25, B 25/25 on labelled synthetic cases | VERIFIED_LOCAL (specification conformance, not real-world accuracy) |
| Evaluation C (validated experience) and D (Memvid behind a flag) | — | — | NOT_DONE (experience memory and Memvid disabled until evaluated) |
| Controlled source ingestion with robots.txt and conditional requests | — | — | NOT_DONE |
| Dockerfile and declarative production config | — | `DEPLOYMENT_PLAN.md` (plan only) | NOT_DONE |
| Demo video pipeline and package | `tools/demo-video/` | `artifacts/demo/validation-report.md`, `youtube-package-validation.md` | VERIFIED_LOCAL as a preview; final video BLOCKED by the live NVIDIA requirement |
