# Deployment plan, cost estimate and runbook (not applied)

`deployment_authorized: false` and no monthly budget were set, so nothing was deployed and no paid resource was created. This is a plan for review.

## Target shape

| Component | Plan | Notes |
|---|---|---|
| Web + API | 2 small containers behind a managed HTTPS load balancer | Stateless; sessions and data in PostgreSQL |
| Worker | 1–2 containers (`python -m policyguard.worker`) | Scale on queue depth; hard maximum, no unlimited autoscaling |
| PostgreSQL | Managed PostgreSQL 16, 2 vCPU, 4–8 GB RAM, point-in-time recovery | Migrations: `alembic upgrade head` as a release step |
| Redis | Managed Redis, smallest tier | Rate limit and cache only; loss is tolerated (fallback limits) |
| Object storage | Private bucket, server-side encryption, no public access | Quarantine and clean prefixes; lifecycle rule deletes rejected uploads |
| Identity | OIDC provider with MFA for policy administrators | BLOCKED: provider not chosen; web uses demo sessions today |
| Inference | Nebius Token Factory, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Budget ledger caps spend; key in a secret manager |

## Monthly cost estimate (assumptions, not quotes)

Inference cost is computed from Nebius list prices ($0.06 / $0.24 per 1M input/output tokens, checked 2026-10-28) and an assumed 1,500 input + 300 output tokens per check: about **$0.00016 per check**, so 10,000 checks ≈ **$1.60** and 100,000 checks ≈ **$16**. Infrastructure prices vary by provider and region (`deployment_region: unset`), so they are not quoted here; the line items above are the small tiers to price once a region is chosen. Load tests against paid infrastructure are not authorized.

## Runbook

| Situation | Signal | Action |
|---|---|---|
| Jobs pile up | `jobs` with state QUEUED growing; `/readyz` ok | Add a worker (bounded); check provider 429s in `inference_runs` |
| Provider outage | `inference_runs.outcome = provider_unavailable_fallback` | No action needed for correctness: checks complete with fixed rules and a visible limitation. Inform users that the AI reader is degraded |
| Dead letters | jobs in DEAD_LETTER | Inspect `last_error`; fix the cause; replay with an `ops_admin` token (`Ops.replay`, audited) |
| Redis down | `/readyz` shows `redis: degraded` | Service continues with stricter local limits; restore Redis |
| Database down | `/readyz` 503; `POST /v1/cases` returns 503 | Nothing is accepted without a durable write; restore from point-in-time backup |
| Policy revoked | admin revokes a version | Cache epoch moves; decisions using it are marked for re-evaluation; experience records invalidated |
| Budget exhausted | `budget_ledger` at limit | Paid calls stop automatically; raise the budget only with approval |

Backup and restore were not tested (no managed database exists); recovery time and data loss are therefore not measured.
