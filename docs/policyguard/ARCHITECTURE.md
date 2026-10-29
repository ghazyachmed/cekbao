# CEKBAO PolicyGuard architecture

Status on 2026-10-28: runs locally (PostgreSQL 16, Redis 8, one web process, one or more workers). Nothing is deployed. "Production-ready" is not claimed.

## Components

```mermaid
flowchart LR
  U[Browser] -->|SSR pages, session cookie, CSRF| W[FastAPI app: app/ + policyguard/web]
  C[API client] -->|JWT ES256, Idempotency-Key| A[/v1 API: policyguard/api]
  W --> S[Application services]
  A --> S
  S -->|one transaction: case + idempotency + outbox| PG[(PostgreSQL)]
  S --> R[(Redis: rate limit, snapshot cache)]
  WK[Worker: python -m policyguard.worker] -->|relay outbox, lease job SKIP LOCKED| PG
  WK -->|instruction as data, strict JSON schema| NB[Nebius Token Factory: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B]
  WK -->|quote grounding + temporal rules| D[Decision + evidence snapshot]
  D --> PG
  S --> OS[(Object store: quarantine -> clean)]
```

## Layers (ports and adapters)

| Layer | Package | Rules |
|---|---|---|
| Domain | `policyguard/domain` | Pure Python. Types, half-open interval selection (strategy: `HalfOpenIntervalSelector`, baseline `LatestRecordedSelector` for evaluation only), deterministic rules. No framework, database or SDK imports |
| Application | `policyguard/application` | Use cases: intake (idempotent submit), worker (process), reviews, policy approval/revocation, operations (replay), uploads, extraction composition. Depends on ports |
| Infrastructure | `policyguard/infra` | PostgreSQL tables and queue, budget ledger, audit chain, Redis cache and limiter, object stores (local, S3), JWT verifier, Nebius adapter, telemetry |
| Interfaces | `policyguard/api`, `policyguard/web` | `/v1` JSON API with OpenAPI; SSR pages mounted into the existing `app.main:create_app` |
| Composition | `policyguard/runtime.py` | Builds adapters from settings for web, API and worker |

## Decision model

Three separate dimensions on every assessment: `policy_decision` (CONSISTENT, CONFLICT, INSUFFICIENT_EVIDENCE, REQUIRES_REVIEW), `evidence_level` (PUBLIC_SOURCE, INSTITUTION_ATTESTED, OFFICIAL_TRANSACTION), `transaction_status` (UNKNOWN unless an authorized transaction system reports otherwise; no such system is connected, so it is always UNKNOWN). A historical assessment (payment already made, judged at its date) and a next-payment assessment (judged at the intended date) are stored as separate decisions.

## Data and time

Valid time: `valid_from <= t < valid_to`; `valid_to = NULL` means the end is unknown; `valid_from = NULL` cannot match any date. Recorded time: `recorded_at` and `revoked_at` define what the system knew (`as_of`). Dates entered by users are converted from local midnight in the stated IANA time zone to UTC; the time zone is stored with the case. Every private table carries `tenant_id`; child queries filter by tenant and case so the composite indexes apply (see `QUERY_PLANS.md`).

## Job states

`ACCEPTED` (case committed) → `QUEUED` (outbox relayed) → `PROCESSING` (leased) → `COMPLETED` | `RETRY_WAIT` (→ `QUEUED`) | `DEAD_LETTER` (via FAILED; the case shows FAILED) ; `QUEUED` → `CANCELLED`. COMPLETED includes INSUFFICIENT_EVIDENCE results. Leases expire after 30 s and are extended by a heartbeat thread; the lease owner fences the decision write; `processed_events(consumer_name, event_id)` deduplicates redelivery; a policy epoch check detects approvals or revocations that land while a job runs.

## Architecture decision records

### ADR-001: Keep Python/FastAPI/Jinja and extend the existing app
Context: the repository already had a working FastAPI app with sessions, CSRF, CSP and 117 passing tests. Decision: add `policyguard/` as a package mounted into `create_app`; no framework migration. Consequences: SSR pages give SEO-capable HTML and work without JavaScript; the existing app keeps its tests and behaviour (223+ tests pass together). Rejected: Next.js rewrite (no blocker shown, duplicate stack).

### ADR-002: PostgreSQL for state, outbox and the job queue
Context: durable intake and at-least-once processing are required; no managed queue is authorized. Decision: transactional outbox in the same database; jobs leased with `FOR UPDATE SKIP LOCKED`; unique constraints for idempotency and deduplication. Consequences: one system to operate locally; throughput bounded by the database (measured plans in `QUERY_PLANS.md`). A managed queue can replace the relay later behind the same job-state contract.

### ADR-003: The model proposes, rules decide
Context: model output can be wrong or manipulated. Decision: the NVIDIA model only extracts fields with verbatim quotes under a strict JSON schema; code grounds every quote; deterministic temporal rules decide. Consequences: a fabricated quote cannot change a decision; provider failures degrade to fixed rules with a visible limitation, never to a fraud verdict.

### ADR-004: Nebius Token Factory with `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
Context: one NVIDIA model through Nebius is required; budget unknown. Decision: the cheapest listed NVIDIA model with strict structured output; paid inference is off unless model, key, budget and call cap are all set; a Postgres ledger with CHECK constraints reserves worst-case cost before each call. See `NVIDIA_NEBIUS.md`.

### ADR-005: Redis for rate limiting and snapshot cache, with conservative fallback
Decision: atomic Lua token bucket per tenant; when Redis is unreachable each instance applies a local limit at one quarter of the burst instead of failing open. Snapshot cache keys include tenant, institution and policy epoch, so approvals and revocations move readers to a new key at once.

### ADR-006: Experience memory and Memvid stay disabled
Context: the brief keeps experience memory and Memvid disabled until evaluated. Decision: `experience_records` are written only from authorized reviewer confirmations and only behind a flag (tested), are invalidated on revocation, and are not read by any decision path. Memvid is not installed; no MemoryStore adapter exists yet. Evaluation C/D has not been run.
