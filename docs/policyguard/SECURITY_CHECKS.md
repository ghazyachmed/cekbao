# Security checks run on 2026-10-28

| Check | Command | Result | Evidence |
|---|---|---|---|
| Known vulnerabilities in Python runtime dependencies | `.venv/bin/pip-audit -r requirements.txt` | No known vulnerabilities found (exit 0) | `evidence/policyguard/security/pip-audit.txt` |
| Software bill of materials | `.venv/bin/cyclonedx-py requirements requirements.txt` | CycloneDX JSON written | `evidence/policyguard/security/sbom-requirements.cdx.json` |
| Lint (new code) | `.venv/bin/ruff check policyguard tests/pgtests scripts/...` with `ruff.toml` | All checks passed | — |
| Types (new code) | `.venv/bin/mypy policyguard --ignore-missing-imports` | No issues in 32 files | — |
| Security behaviour tests | `pytest tests/pgtests` (tenant isolation, IDOR, CSRF, uploads, JWT, rate limits, injection, budget) | Pass (see full suite count in the final report) | `tests/pgtests/` |

Not run: npm audit of the Node tool workspaces (development-only tools, versions pinned to the existing `video/` lockfile), dynamic scanning (DAST), dependency audit of the pre-existing `app/` baseline beyond the shared requirements file.
