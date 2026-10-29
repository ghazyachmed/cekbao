"""PostgreSQL adapters: policy snapshots, job queue, budget ledger and audit log."""
from __future__ import annotations

import hashlib
import json
import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import Connection, Engine, insert, select, text, update

from policyguard.application.errors import BudgetExhausted
from policyguard.domain.model import (
    ApprovalStatus,
    AuthorityGrant,
    Citation,
    EvidenceLevel,
    Institution,
    PayeeDetails,
    PolicyVersion,
)

from . import tables as t

Clock = Callable[[], datetime]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def jdump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


# ----------------------------------------------------------------- snapshots

def institution_from_row(r) -> Institution:
    return Institution(r.institution_id, r.tenant_id, r.name, r.timezone, r.official_contact_url,
                       tuple(r.aliases or ()), r.synthetic)


def grant_from_row(r) -> AuthorityGrant:
    return AuthorityGrant(r.grant_id, r.tenant_id, r.institution_id, r.issuer_id, r.authority_scope,
                          r.verification_method, EvidenceLevel(r.evidence_level), r.valid_from, r.valid_to,
                          r.recorded_at, r.revoked_at)


def version_from_row(r) -> PolicyVersion:
    p, c = r.payee, r.citation
    return PolicyVersion(
        tenant_id=r.tenant_id, institution_id=r.institution_id, policy_id=r.policy_id, version_id=r.version_id,
        version_label=r.version_label, source_url=r.source_url, source_hash=r.source_hash, issuer_id=r.issuer_id,
        authority_scope=r.authority_scope, verification_method=r.verification_method,
        evidence_level=EvidenceLevel(r.evidence_level), valid_from=r.valid_from, valid_to=r.valid_to,
        valid_tz=r.valid_tz, recorded_at=r.recorded_at,
        payee=PayeeDetails(p["payee_name"], p["account_number"], p["currency"], p.get("bank_name"), p.get("swift_bic"),
                           tuple(p.get("channels") or ("bank_transfer",))),
        citation=Citation(c["source_id"], c["source_url"], c["source_title"], c["quote"], c["locator"], c["language"],
                          c.get("translation")),
        approval_status=ApprovalStatus(r.approval_status), supersedes_version_id=r.supersedes_version_id,
        revoked_at=r.revoked_at, fetched_at=r.fetched_at, verified_at=r.verified_at,
        freshness_deadline=r.freshness_deadline, document_object_key=r.document_object_key,
        extraction_version=r.extraction_version, synthetic=r.synthetic)


@dataclass(frozen=True)
class Snapshot:
    institution: Institution | None
    versions: tuple[PolicyVersion, ...]
    grants: tuple[AuthorityGrant, ...]
    epoch: int
    raw: dict    # JSON form, stored with every decision as the evidence snapshot


class SnapshotCache(Protocol):
    def get(self, key: str) -> dict | None: ...
    def set(self, key: str, value: dict, ttl_s: int) -> None: ...


class InMemoryCache:
    def __init__(self):
        self.data: dict[str, dict] = {}

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def set(self, key: str, value: dict, ttl_s: int) -> None:
        self.data[key] = value


def _row_json(row) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row._mapping.items()}


class _Row:
    """Attribute access over a JSON dict, so cached snapshots rebuild through the same functions."""

    def __init__(self, d: dict):
        self.__dict__.update({k: (datetime.fromisoformat(v) if isinstance(v, str) and k.endswith(("_at", "_from", "_to",
                                                                                                   "_deadline"))
                                  else v) for k, v in d.items()})


class PolicySnapshots:
    def __init__(self, engine: Engine, cache: SnapshotCache | None = None, ttl_s: int = 300):
        self.engine, self.cache, self.ttl_s = engine, cache, ttl_s

    @staticmethod
    def key(tenant_id: str, institution_id: str, epoch: int) -> str:
        return f"pg:v1:{tenant_id}:{institution_id}:{epoch}:snapshot"

    def epoch(self, conn: Connection, tenant_id: str, institution_id: str, lock: bool = False) -> int | None:
        q = select(t.institutions.c.policy_epoch).where(t.institutions.c.tenant_id == tenant_id,
                                                         t.institutions.c.institution_id == institution_id)
        if lock:
            q = q.with_for_update(read=True)
        return conn.execute(q).scalar_one_or_none()

    def load(self, tenant_id: str, institution_id: str | None) -> Snapshot:
        if institution_id is None:
            return Snapshot(None, (), (), 0, {"institution": None, "versions": [], "grants": [], "epoch": 0})
        with self.engine.connect() as conn:
            epoch = self.epoch(conn, tenant_id, institution_id)
            if epoch is None:
                return Snapshot(None, (), (), 0, {"institution": None, "versions": [], "grants": [], "epoch": 0})
            key = self.key(tenant_id, institution_id, epoch)
            raw = self.cache.get(key) if self.cache else None
            if raw is None:
                inst = conn.execute(select(t.institutions).where(t.institutions.c.institution_id == institution_id)).one()
                versions = conn.execute(select(t.policy_versions).where(
                    t.policy_versions.c.tenant_id == tenant_id, t.policy_versions.c.institution_id == institution_id)
                    .order_by(t.policy_versions.c.policy_id, t.policy_versions.c.valid_from)).all()
                grants = conn.execute(select(t.authority_grants).where(
                    t.authority_grants.c.tenant_id == tenant_id,
                    t.authority_grants.c.institution_id == institution_id)).all()
                raw = {"institution": _row_json(inst), "versions": [_row_json(v) for v in versions],
                       "grants": [_row_json(g) for g in grants], "epoch": epoch}
                if self.cache:
                    self.cache.set(key, raw, self.ttl_s)
        return Snapshot(institution_from_row(_Row(raw["institution"])),
                        tuple(version_from_row(_Row(v)) for v in raw["versions"]),
                        tuple(grant_from_row(_Row(g)) for g in raw["grants"]), raw["epoch"], raw)


# ----------------------------------------------------------------- queue

@dataclass(frozen=True)
class Job:
    job_id: str
    tenant_id: str
    case_id: str
    source_event_id: str
    attempts: int
    max_attempts: int
    traceparent: str | None


def _job(r) -> Job:
    return Job(r.job_id, r.tenant_id, r.case_id, r.source_event_id, r.attempts, r.max_attempts, r.traceparent)


def set_case_state(conn: Connection, case_id: str, state: str, now: datetime, **extra) -> None:
    conn.execute(update(t.cases).where(t.cases.c.case_id == case_id)
                 .values(state=state, updated_at=now, row_version=t.cases.c.row_version + 1, **extra))


class PgJobQueue:
    """Durable queue on PostgreSQL. Leases use FOR UPDATE SKIP LOCKED; the lease owner fences every write."""

    def __init__(self, engine: Engine, clock: Clock, lease_s: int, max_attempts: int, deadline_s: int,
                 rng: random.Random | None = None, backoff_base_s: float = 2.0, backoff_cap_s: float = 60.0):
        self.engine, self.clock = engine, clock
        self.lease_s, self.max_attempts, self.deadline_s = lease_s, max_attempts, deadline_s
        self.rng = rng or random.Random()
        self.base, self.cap = backoff_base_s, backoff_cap_s

    def relay_outbox(self, limit: int = 100) -> int:
        """Outbox -> jobs. At-least-once: a re-delivered event hits the unique source_event_id and is ignored."""
        now = self.clock()
        with self.engine.begin() as conn:
            events = conn.execute(select(t.outbox_events).where(
                t.outbox_events.c.status == "PENDING", t.outbox_events.c.available_at <= now)
                .order_by(t.outbox_events.c.available_at).limit(limit).with_for_update(skip_locked=True)).all()
            for e in events:
                created = conn.execute(text(
                    "INSERT INTO jobs (job_id, tenant_id, case_id, source_event_id, state, attempts, max_attempts, "
                    "run_after, deadline_at, traceparent, created_at, updated_at) VALUES (:id, :tenant, :case, :ev, "
                    "'QUEUED', 0, :max, :now, :deadline, :tp, :now, :now) ON CONFLICT (source_event_id) DO NOTHING "
                    "RETURNING job_id"), dict(id=new_id("job"), tenant=e.tenant_id, case=e.case_id, ev=e.event_id,
                                              max=self.max_attempts, now=now, tp=e.traceparent,
                                              deadline=now + timedelta(seconds=self.deadline_s))).first()
                if created:
                    conn.execute(update(t.cases).where(t.cases.c.case_id == e.case_id, t.cases.c.state == "ACCEPTED")
                                 .values(state="QUEUED", updated_at=now, row_version=t.cases.c.row_version + 1))
                conn.execute(update(t.outbox_events).where(t.outbox_events.c.event_id == e.event_id)
                             .values(status="PUBLISHED", published_at=now, attempts=t.outbox_events.c.attempts + 1))
        return len(events)

    def lease(self, owner: str) -> Job | None:
        now = self.clock()
        with self.engine.begin() as conn:
            # RETRY_WAIT -> QUEUED when due; PROCESSING with an expired lease -> QUEUED (the worker died).
            for state, cond in (("RETRY_WAIT", "run_after <= :now"), ("PROCESSING", "lease_expires_at < :now")):
                ids = conn.execute(text(f"UPDATE jobs SET state='QUEUED', lease_owner=NULL, updated_at=:now "
                                        f"WHERE job_id IN (SELECT job_id FROM jobs WHERE state='{state}' AND {cond} "
                                        f"FOR UPDATE SKIP LOCKED) RETURNING case_id"), {"now": now}).scalars().all()
                for case_id in ids:
                    set_case_state(conn, case_id, "QUEUED", now)
            row = conn.execute(text(
                "UPDATE jobs SET state='PROCESSING', attempts=attempts+1, lease_owner=:owner, lease_expires_at=:exp, "
                "updated_at=:now WHERE job_id = (SELECT job_id FROM jobs WHERE state='QUEUED' AND run_after <= :now "
                "ORDER BY run_after, job_id LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *"),
                {"owner": owner, "now": now, "exp": now + timedelta(seconds=self.lease_s)}).first()
            if row is None:
                return None
            if row.deadline_at < now:
                self._dead_letter(conn, row.job_id, row.case_id, "deadline_exceeded", now)
                return None
            set_case_state(conn, row.case_id, "PROCESSING", now)
            return _job(row)

    def heartbeat(self, job_id: str, owner: str) -> bool:
        now = self.clock()
        with self.engine.begin() as conn:
            res = conn.execute(update(t.jobs).where(t.jobs.c.job_id == job_id, t.jobs.c.lease_owner == owner,
                                                    t.jobs.c.state == "PROCESSING")
                               .values(lease_expires_at=now + timedelta(seconds=self.lease_s), updated_at=now))
            return res.rowcount == 1

    def holds_lease(self, conn: Connection, job_id: str, owner: str) -> bool:
        row = conn.execute(select(t.jobs.c.state, t.jobs.c.lease_owner).where(t.jobs.c.job_id == job_id)
                           .with_for_update()).first()
        return row is not None and row.state == "PROCESSING" and row.lease_owner == owner

    def complete(self, conn: Connection, job_id: str) -> None:
        conn.execute(update(t.jobs).where(t.jobs.c.job_id == job_id).values(
            state="COMPLETED", lease_owner=None, lease_expires_at=None, updated_at=self.clock()))

    def backoff(self, attempts: int, retry_after: float | None) -> float:
        jitter = self.rng.uniform(0, min(self.cap, self.base * (2 ** attempts)))   # full jitter
        return max(retry_after or 0.0, jitter, 1.0)

    def retry_or_dead_letter(self, job: Job, owner: str, error: str, retry_after: float | None) -> str:
        now = self.clock()
        with self.engine.begin() as conn:
            if not self.holds_lease(conn, job.job_id, owner):
                return "lease_lost"
            if job.attempts >= job.max_attempts:
                self._dead_letter(conn, job.job_id, job.case_id, error, now)
                return "DEAD_LETTER"
            run_after = now + timedelta(seconds=self.backoff(job.attempts, retry_after))
            conn.execute(update(t.jobs).where(t.jobs.c.job_id == job.job_id).values(
                state="RETRY_WAIT", run_after=run_after, last_error=error[:200], lease_owner=None,
                lease_expires_at=None, updated_at=now))
            set_case_state(conn, job.case_id, "RETRY_WAIT", now)
            return "RETRY_WAIT"

    def dead_letter(self, job: Job, owner: str, error: str) -> bool:
        with self.engine.begin() as conn:
            if not self.holds_lease(conn, job.job_id, owner):
                return False
            self._dead_letter(conn, job.job_id, job.case_id, error, self.clock())
            return True

    def _dead_letter(self, conn: Connection, job_id: str, case_id: str, error: str, now: datetime) -> None:
        # PROCESSING -> FAILED -> DEAD_LETTER. Permanent errors are not retried.
        conn.execute(update(t.jobs).where(t.jobs.c.job_id == job_id).values(
            state="DEAD_LETTER", last_error=error[:200], lease_owner=None, lease_expires_at=None, updated_at=now))
        set_case_state(conn, case_id, "FAILED", now)

    def replay(self, conn: Connection, job_id: str) -> str:
        now = self.clock()
        row = conn.execute(update(t.jobs).where(t.jobs.c.job_id == job_id, t.jobs.c.state == "DEAD_LETTER").values(
            state="QUEUED", attempts=0, run_after=now, deadline_at=now + timedelta(seconds=self.deadline_s),
            last_error=None, updated_at=now).returning(t.jobs.c.case_id)).first()
        if row is None:
            raise LookupError("job is not in DEAD_LETTER")
        set_case_state(conn, row.case_id, "QUEUED", now)
        return row.case_id


# ----------------------------------------------------------------- budget

class PgBudgetLedger:
    """Reservation before every paid call. CHECK constraints make overspending impossible across instances."""

    def __init__(self, engine: Engine, scope: str = "global"):
        self.engine, self.scope = engine, scope

    def configure(self, limit_usd: Decimal, max_calls: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO budget_ledger (scope, limit_usd, max_calls) VALUES (:s, :l, :m) "
                              "ON CONFLICT (scope) DO UPDATE SET limit_usd = EXCLUDED.limit_usd, "
                              "max_calls = EXCLUDED.max_calls"), {"s": self.scope, "l": limit_usd, "m": max_calls})

    def reserve(self, usd: Decimal) -> str:
        with self.engine.begin() as conn:
            row = conn.execute(text(
                "UPDATE budget_ledger SET reserved_usd = reserved_usd + :u, calls = calls + 1 WHERE scope = :s "
                "AND reserved_usd + spent_usd + :u <= limit_usd AND calls + 1 <= max_calls RETURNING scope"),
                {"u": usd, "s": self.scope}).first()
        if row is None:
            raise BudgetExhausted(self.scope)
        return self.scope

    def settle(self, reservation: str, usd: Decimal, actual_usd: Decimal) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE budget_ledger SET reserved_usd = GREATEST(reserved_usd - :u, 0), "
                              "spent_usd = spent_usd + :a WHERE scope = :s"),
                         {"u": usd, "a": actual_usd, "s": reservation})

    def release(self, reservation: str, usd: Decimal) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE budget_ledger SET reserved_usd = GREATEST(reserved_usd - :u, 0), "
                              "calls = GREATEST(calls - 1, 0) WHERE scope = :s"), {"u": usd, "s": reservation})

    def state(self) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(t.budget_ledger).where(t.budget_ledger.c.scope == self.scope)).first()
        return None if row is None else {k: (str(v) if isinstance(v, Decimal) else v) for k, v in row._mapping.items()}


# ----------------------------------------------------------------- audit

def append_audit(conn: Connection, tenant_id: str, actor: str, action: str, target: str, details: dict,
                 now: datetime) -> str:
    """Hash-chained, append-only per tenant. A per-tenant advisory lock serializes the chain."""
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:t))"), {"t": tenant_id})
    prev = conn.execute(select(t.audit_entries.c.entry_hash).where(t.audit_entries.c.tenant_id == tenant_id)
                        .order_by(t.audit_entries.c.entry_id.desc()).limit(1)).scalar_one_or_none() or "0" * 64
    body = jdump({"tenant": tenant_id, "actor": actor, "action": action, "target": target, "details": details,
                  "at": now.isoformat(), "prev": prev})
    digest = hashlib.sha256(body.encode()).hexdigest()
    conn.execute(insert(t.audit_entries).values(tenant_id=tenant_id, actor=actor, action=action, target=target,
                                                details=details, at=now, prev_hash=prev, entry_hash=digest))
    return digest
