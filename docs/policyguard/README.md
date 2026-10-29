# CEKBAO PolicyGuard documentation

| Document | Contents |
|---|---|
| [AUDIT.md](AUDIT.md) | Baseline before this work, real vs stub vs synthetic, risks, primary sources |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, layers, decision model, job states, ADR-001 to ADR-006 |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Threats, controls, tests, residual risk |
| [DESIGN.md](DESIGN.md) | Visual direction, typography, tokens, components, accessibility, content rules, skills used |
| [CONTRAST.md](CONTRAST.md) | Measured WCAG contrast for every colour pair (generated) |
| [NVIDIA_NEBIUS.md](NVIDIA_NEBIUS.md) | Model choice, license (open weight), cost bound, live-test procedure and status |
| [EVALUATION.md](EVALUATION.md) | A (newest version) vs B (temporal selection) on labelled synthetic cases |
| [QUERY_PLANS.md](QUERY_PLANS.md) | EXPLAIN ANALYZE on 100,000 synthetic cases (generated) |
| [SECURITY_CHECKS.md](SECURITY_CHECKS.md) | pip-audit, SBOM, lint and type results |
| [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md) | Plan, inference cost estimate, runbook (nothing deployed) |
| [TRACEABILITY.md](TRACEABILITY.md) | Requirement → code → test → evidence → status |
| [UI_TRACEABILITY.md](UI_TRACEABILITY.md) | User task → screen → test, with user-validation status kept separate |

## Run it locally

```bash
scripts/policyguard_serve.sh
```

Starts local PostgreSQL and Redis (`.local/`), applies migrations, seeds synthetic data, starts one worker and serves the app on http://127.0.0.1:8780. Sign in at `/check/sign-in` with a synthetic demo account listed on that page.

```bash
.venv/bin/python -m pytest -q
```

Runs the existing and PolicyGuard tests (PostgreSQL and Redis must be running for the integration tests).
