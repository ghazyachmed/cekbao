# Initial audit: CEKBAO PolicyGuard

Date: 2026-10-28. Repository: `/Users/ghazy/Ghazy/cekbao`, commit `745bb1f`. Mode: `repair_existing` (the repository exists and works).

## 1. Baseline measured on 2026-10-28 (before PolicyGuard)

| Check | Command | Result |
|---|---|---|
| Tests | `.venv/bin/python -m pytest -q` | 117 passed, exit 0 |
| Sandbox scenarios | `.venv/bin/python scripts/run_scenarios.py` | 18/18, exit 0 |
| Lint | `ruff check app tests scripts` (machine-wide settings; no project config existed) | 78 findings in existing code |
| Types | `mypy app` | 15 errors in `app/workflow.py`, `app/main.py`, `app/settlement.py` |
| Web build | none (Jinja2 + static JS) | n/a |
| Migrations | none; SQLite schema via `CREATE TABLE IF NOT EXISTS` | risk |

Evidence: `evidence/policyguard/baseline_lint_typecheck.txt`. Earlier conversation results were not reused as evidence.

## 2. What was real, stubbed or synthetic

| Part | Status | Note |
|---|---|---|
| `app/` FastAPI monolith (SQLite) | real, tested locally | single process, single file database, no tenants |
| Institution registry | synthetic | `fixtures/registry.json`, no validity periods |
| Sender, link, payee, account and SWIFT matching | real, deterministic | no policy versions or time intervals |
| Slip-to-ledger reconciliation | real code, synthetic data | ledger and bank feed are fixtures |
| LLM adapter | stub tested with mocks | no real model call |
| Sessions, CSRF, roles | real (demo sign-in) | not OIDC, no MFA |
| Queue, worker, outbox, object storage, distributed limiter, telemetry | absent | analysis ran inside the HTTP request |
| `video/` (Remotion) | real | earlier demo video; not part of the runtime |

## 3. Gap

PolicyGuard needs time-aware policies (valid and recorded time), issuer authority, tenancy, durable intake (202 + outbox), a separate worker and three separate decision dimensions. Adding these to the SQLite model in `app/` would mix two domains and break its 117 tests, so PolicyGuard is a new package mounted into the same app.

## 4. Risks, highest first

1. Wrong temporal decision (an old policy used for a new payment).
2. Tenant data leakage.
3. Over-claiming ("safe", "settled") from text, screenshots or hashes.
4. Lost or duplicated work.
5. Prompt injection and fabricated model quotes.
6. SSRF in source ingestion.
7. Uncontrolled inference cost.
8. Dependency and secret hygiene.

Mitigations and tests: `THREAT_MODEL.md`, `TRACEABILITY.md`.

## 5. Primary sources checked (2026-10-28)

| Topic | Source | Finding |
|---|---|---|
| Nebius inference | https://docs.tokenfactory.nebius.com/ | Base URL `https://api.tokenfactory.nebius.com/v1/`; key in `NEBIUS_API_KEY` |
| Model list | https://docs.tokenfactory.nebius.com/api-reference/examples/list-of-models.md | Only via `GET /v1/models` with a key |
| NVIDIA models on Nebius | https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` listed with prices |
| Model license | https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/ | NVIDIA Nemotron Open Model License; open weights, not OSI open source |
| Structured output | https://docs.tokenfactory.nebius.com/ai-models-inference/json.md | `json_schema` with `strict` |
| Rate limits | https://docs.tokenfactory.nebius.com/ai-models-inference/rate-limits.md | 429 with `Retry-After` |
| Hackathon rules | Official brochure: https://www.pol.cmu.ac.th/public/blog/attachment/download/7a51866a-4cee-42b5-9187-fa4e1f4df411 (re-read 2026-10-28) | Demo video optional, no longer than 5 minutes; English; submission deadline 20 October 2026 (passed); finalists announced 31 October |
| YouTube limits | YouTube Help (chapters 9884579, thumbnails 72431, video settings 57404) | Title 100, description 5,000 characters; chapters from 00:00, at least three, each at least 10 s; thumbnails 16:9, up to 2 MB on mobile |
| STAIR | arXiv search | Closest candidate arXiv 2608.09524; identity not confirmed; label "STAIR-inspired" |
| Memvid | https://pypi.org/project/memvid-sdk/ | Not installed; disabled until evaluated |
