"""EXPLAIN ANALYZE on representative synthetic data (100,000 cases) for the queries the application runs.

Uses a separate local database (policyguard_perf) so tests and the demo are not affected.
Writes docs/policyguard/QUERY_PLANS.md. Usage: .venv/bin/python scripts/policyguard_query_plans.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

URL = "postgresql+psycopg://policyguard@127.0.0.1:55432/policyguard_perf"
PGBIN = "/opt/homebrew/opt/postgresql@16/bin"

SEED = """
INSERT INTO tenants (tenant_id, name) SELECT 't' || g, 'Synthetic tenant ' || g FROM generate_series(1, 50) g;
INSERT INTO institutions (institution_id, tenant_id, name, timezone, synthetic)
  SELECT 'i' || g, 't' || (1 + g % 50), 'Synthetic institution ' || g, 'UTC', true FROM generate_series(1, 1000) g;
INSERT INTO source_documents (source_id, tenant_id, institution_id, url, title, issuer_id, language, content_hash,
  fetched_at, synthetic)
  SELECT 's' || g, 't' || (1 + g % 50), 'i' || g, 'https://example.invalid/' || g, 'src', 'issuer', 'en', 'h', now(), true
  FROM generate_series(1, 1000) g;
INSERT INTO policy_versions (version_id, tenant_id, institution_id, policy_id, version_label, source_id, source_url,
  source_hash, issuer_id, authority_scope, verification_method, evidence_level, valid_from, valid_to, valid_tz,
  recorded_at, extraction_version, approval_status, payee, citation, synthetic)
  SELECT 'v' || i || '_' || v, 't' || (1 + i % 50), 'i' || i, 'p' || i, v::text, 's' || i, 'u', 'h', 'issuer', 'scope', 'm',
    'PUBLIC_SOURCE', timestamptz '2020-01-01' + (v || ' years')::interval,
    CASE WHEN v < 5 THEN timestamptz '2020-01-01' + ((v + 1) || ' years')::interval END, 'UTC', now(), 'x', 'APPROVED',
    '{}'::jsonb, '{}'::jsonb, true
  FROM generate_series(1, 1000) i, generate_series(0, 5) v;
INSERT INTO cases (case_id, tenant_id, created_by, institution_id, instruction_text, instruction_sha256, state,
  request_hash, created_at, updated_at)
  SELECT 'c' || g, 't' || (1 + g % 50), 'u' || (g % 2000), 'i' || (1 + g % 1000), 'synthetic', md5(g::text), 'COMPLETED',
    md5(g::text), now() - (g || ' minutes')::interval, now()
  FROM generate_series(1, 100000) g;
INSERT INTO idempotency_requests (tenant_id, idempotency_key, request_hash, case_id)
  SELECT 't' || (1 + g % 50), 'k' || g, md5(g::text), 'c' || g FROM generate_series(1, 100000) g;
INSERT INTO outbox_events (event_id, tenant_id, case_id, event_type, schema_version, payload, occurred_at, status, available_at)
  SELECT 'e' || g, 't' || (1 + g % 50), 'c' || g, 'case.submitted', 1, '{}'::jsonb, now(),
    CASE WHEN g <= 100 THEN 'PENDING' ELSE 'PUBLISHED' END, now() - (g || ' seconds')::interval
  FROM generate_series(1, 100000) g;
INSERT INTO jobs (job_id, tenant_id, case_id, source_event_id, state, max_attempts, run_after, deadline_at)
  SELECT 'j' || g, 't' || (1 + g % 50), 'c' || g, 'e' || g, CASE WHEN g <= 100 THEN 'QUEUED' ELSE 'COMPLETED' END, 3,
    now() - (g || ' seconds')::interval, now() + interval '1 hour'
  FROM generate_series(1, 100000) g;
INSERT INTO decisions (decision_id, tenant_id, case_id, assessment_kind, policy_decision, transaction_status, next_action,
  findings, limitations, applied_version_ids, considered_version_ids, claim, evidence_snapshot, rule_version,
  model_version, request_hash, policy_epoch)
  SELECT 'd' || g, 't' || (1 + g % 50), 'c' || g, 'NEXT_PAYMENT',
    (ARRAY['CONSISTENT','CONFLICT','INSUFFICIENT_EVIDENCE','REQUIRES_REVIEW'])[1 + g % 4], 'UNKNOWN', 'x',
    '[]', '[]', '[]', '[]', '{}', '{}', 'r', 'm', md5(g::text), 0
  FROM generate_series(1, 100000) g;
ANALYZE;
"""

QUERIES = [
    ("Case list for one tenant, newest first (cursor page)",
     "SELECT case_id, state, created_at FROM cases WHERE tenant_id = 't7' "
     "AND (created_at, case_id) < (now() - interval '10 days', 'c999999') ORDER BY created_at DESC, case_id DESC LIMIT 50"),
    ("Policy snapshot for one institution",
     "SELECT * FROM policy_versions WHERE tenant_id = 't8' AND institution_id = 'i7' ORDER BY policy_id, valid_from"),
    ("Outbox relay batch",
     "SELECT * FROM outbox_events WHERE status = 'PENDING' AND available_at <= now() ORDER BY available_at LIMIT 100 "
     "FOR UPDATE SKIP LOCKED"),
    ("Idempotency lookup",
     "SELECT request_hash, case_id FROM idempotency_requests WHERE tenant_id = 't8' AND idempotency_key = 'k12357'"),
    ("Job lease candidate",
     "SELECT job_id FROM jobs WHERE state = 'QUEUED' AND run_after <= now() ORDER BY run_after, job_id LIMIT 1 "
     "FOR UPDATE SKIP LOCKED"),
    ("Decisions of one case",
     "SELECT * FROM decisions WHERE tenant_id = 't43' AND case_id = 'c4242' ORDER BY created_at, assessment_kind"),
    ("Review queue page (needs review) for one tenant",
     "SELECT c.case_id, (SELECT d.policy_decision FROM decisions d WHERE d.tenant_id = c.tenant_id AND d.case_id = c.case_id "
     "ORDER BY d.created_at DESC LIMIT 1) FROM cases c WHERE c.tenant_id = 't7' AND EXISTS (SELECT 1 FROM decisions d "
     "WHERE d.tenant_id = c.tenant_id AND d.case_id = c.case_id AND d.policy_decision IN ('REQUIRES_REVIEW', "
     "'INSUFFICIENT_EVIDENCE')) ORDER BY c.created_at DESC, c.case_id DESC LIMIT 50"),
]


def main() -> None:
    subprocess.run([f"{PGBIN}/dropdb", "-h", "127.0.0.1", "-p", "55432", "-U", "policyguard", "--if-exists",
                    "policyguard_perf"], check=True)
    subprocess.run([f"{PGBIN}/createdb", "-h", "127.0.0.1", "-p", "55432", "-U", "policyguard", "policyguard_perf"],
                   check=True)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["url"] = URL
    command.upgrade(cfg, "head")
    engine = create_engine(URL)
    started = time.monotonic()
    with engine.begin() as conn:
        for stmt in [s for s in SEED.split(";\n") if s.strip()]:
            conn.execute(text(stmt))
    seed_s = time.monotonic() - started
    out = ["# Query plans on 100,000 synthetic cases", "",
           f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} by `scripts/policyguard_query_plans.py` "
           f"on local PostgreSQL 16 (Apple M2, default settings). Seed time {seed_s:.1f} s.", "",
           "Data: 50 tenants, 1,000 institutions, 6,000 policy versions, 100,000 cases, 100,000 idempotency records, "
           "100,000 outbox events (100 pending), 100,000 jobs (100 queued), 100,000 decisions.", "",
           "Each plan is `EXPLAIN (ANALYZE, BUFFERS)` of the query the application runs. Times are single local runs "
           "after ANALYZE, not production measurements.", ""]
    with engine.begin() as conn:
        sizes = conn.execute(text("SELECT relname, pg_size_pretty(pg_relation_size(indexrelid)) FROM pg_stat_user_indexes "
                                  "ORDER BY pg_relation_size(indexrelid) DESC LIMIT 12")).all()
        for title, sql in QUERIES:
            plan = "\n".join(r[0] for r in conn.execute(text("EXPLAIN (ANALYZE, BUFFERS) " + sql)))
            out += [f"## {title}", "", "```sql", sql, "```", "", "```", plan, "```", ""]
    out += ["## Largest indexes (write cost)", "", "| Table | Index size |", "|---|---|",
            *[f"| {r[0]} | {r[1]} |" for r in sizes], "",
            "Every insert into cases, outbox_events, jobs and idempotency_requests updates its B-tree indexes "
            "(O(log n) each). No GiST range index was added: interval selection reads at most a few versions per "
            "institution through `ix_policy_versions_institution_id_policy_id_valid_from`, so a range index has no "
            "measured benefit yet.", ""]
    (ROOT / "docs" / "policyguard" / "QUERY_PLANS.md").write_text("\n".join(out))
    print("\n".join(line for line in out if "Execution Time" in line or line.startswith("## ")))


if __name__ == "__main__":
    main()
