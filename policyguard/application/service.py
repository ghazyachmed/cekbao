"""Application services: intake, worker, reviews, policy approval and operations.

Transaction boundaries:
1. submit: case + idempotency record + outbox event, one transaction (202 only after commit).
2. relay: outbox -> job, idempotent on event_id.
3. process: extraction runs outside any transaction; the decision write is one transaction fenced by the
   job lease, deduplicated through processed_events and checked against the institution policy epoch.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Engine, insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.sanitize import InputRejected, detect_injection, sanitize_text
from policyguard.config import PGSettings
from policyguard.domain import normalize
from policyguard.domain.model import Assessment, Claim, EvaluationContext
from policyguard.domain.rules import assess_case
from policyguard.infra import tables as t
from policyguard.infra.pg import (
    InMemoryCache,
    Job,
    PgBudgetLedger,
    PgJobQueue,
    PolicySnapshots,
    SnapshotCache,
    append_audit,
    jdump,
    new_id,
    set_case_state,
)

from .errors import (
    ConcurrencyConflict,
    DurableWriteUnavailable,
    EpochChanged,
    Forbidden,
    IdempotencyConflict,
    NotFound,
    TransientModelError,
    ValidationFailed,
)
from .extraction import ClaimExtraction, ClaimExtractor, PaidClaimModel, RulesExtractor, Usage, apply_corrections

CONSUMER = "case-verifier.v1"
MAX_INSTRUCTION_CHARS = 20_000
REVIEW_OUTCOMES = ("CONFIRMED", "CORRECTED", "NEEDS_MORE_INFORMATION")
READ_ALL_ROLES = {"reviewer", "ops_admin", "policy_admin"}


@dataclass(frozen=True)
class Actor:
    user_id: str
    tenant_id: str
    roles: frozenset[str]
    mfa: bool = False


@dataclass(frozen=True)
class CaseInput:
    instruction_text: str
    institution_id: str | None = None
    institution_query: str | None = None
    instruction_received_on: str | None = None   # YYYY-MM-DD, when the user received the instruction
    paid_on: str | None = None                   # YYYY-MM-DD, a payment already made (historical check)
    due_on: str | None = None                    # YYYY-MM-DD, the intended payment date (next-payment check)
    payment_tz: str = "UTC"
    corrections: dict[str, str] = field(default_factory=dict)
    upload_ids: tuple[str, ...] = ()

    def canonical(self) -> dict:
        d = asdict(self)
        d["upload_ids"] = sorted(d["upload_ids"])
        return d


@dataclass(frozen=True)
class SubmitResult:
    case_id: str
    state: str
    request_hash: str
    replayed: bool


def request_hash(payload: CaseInput) -> str:
    return hashlib.sha256(jdump(payload.canonical()).encode()).hexdigest()


def _local_midnight(value: str | None, tz: str, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise ValidationFailed("Use a full date such as 2026-11-15.", field_name) from None
    return datetime.combine(d, time(0), ZoneInfo(tz)).astimezone(UTC)


def new_traceparent() -> str:
    from policyguard.infra.telemetry import current_traceparent
    return current_traceparent() or f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, (datetime, date)) else v


class IntakeService:
    def __init__(self, engine: Engine, clock: Callable[[], datetime]):
        self.engine, self.clock = engine, clock

    def validate(self, actor: Actor, payload: CaseInput) -> CaseInput:
        if "payer" not in actor.roles and "reviewer" not in actor.roles:
            raise Forbidden("Your role cannot submit checks.")
        try:
            clean = sanitize_text(payload.instruction_text or "", MAX_INSTRUCTION_CHARS).text
        except InputRejected as e:
            raise ValidationFailed(str(e), "instruction_text") from None
        if len(clean.strip()) < 20:
            raise ValidationFailed("Paste the full payment instruction (at least 20 characters).", "instruction_text")
        try:
            ZoneInfo(payload.payment_tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationFailed("Choose a valid time zone.", "payment_tz") from None
        if not payload.institution_id and not (payload.institution_query or "").strip():
            raise ValidationFailed("Choose an institution, or select that it is not listed and type its name.",
                                   "institution_id")
        for name in ("instruction_received_on", "paid_on", "due_on"):
            _local_midnight(getattr(payload, name), payload.payment_tz, name)
        unknown = set(payload.corrections) - set(Claim.FIELDS)
        if unknown:
            raise ValidationFailed(f"Unknown correction field: {sorted(unknown)[0]}", "corrections")
        return payload

    def submit(self, actor: Actor, idempotency_key: str, payload: CaseInput) -> SubmitResult:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValidationFailed("Idempotency-Key header is required (max 128 characters).", "Idempotency-Key")
        payload = self.validate(actor, payload)
        rhash = request_hash(payload)
        try:
            return self._submit(actor, idempotency_key, payload, rhash)
        except IntegrityError:
            # Another instance committed the same key first. Return its case, or 409 if the payload differs.
            existing = self._existing(actor.tenant_id, idempotency_key)
            if existing is None:
                raise DurableWriteUnavailable("could not store the case") from None
            return self._replay(existing, rhash)
        except DBAPIError as e:
            raise DurableWriteUnavailable("The check could not be saved. Nothing was submitted.") from e

    def _existing(self, tenant_id: str, key: str):
        with self.engine.connect() as conn:
            return conn.execute(select(t.idempotency_requests.c.request_hash, t.idempotency_requests.c.case_id,
                                       t.cases.c.state)
                                .join(t.cases, t.cases.c.case_id == t.idempotency_requests.c.case_id)
                                .where(t.idempotency_requests.c.tenant_id == tenant_id,
                                       t.idempotency_requests.c.idempotency_key == key)).first()

    @staticmethod
    def _replay(existing, rhash: str) -> SubmitResult:
        if existing.request_hash != rhash:
            raise IdempotencyConflict("This Idempotency-Key was already used with a different request.")
        return SubmitResult(existing.case_id, existing.state, rhash, True)

    def _submit(self, actor: Actor, key: str, p: CaseInput, rhash: str) -> SubmitResult:
        now = self.clock()
        with self.engine.begin() as conn:
            existing = conn.execute(select(t.idempotency_requests.c.request_hash, t.idempotency_requests.c.case_id,
                                           t.cases.c.state)
                                    .join(t.cases, t.cases.c.case_id == t.idempotency_requests.c.case_id)
                                    .where(t.idempotency_requests.c.tenant_id == actor.tenant_id,
                                           t.idempotency_requests.c.idempotency_key == key)).first()
            if existing:
                return self._replay(existing, rhash)
            inst_id = p.institution_id
            if inst_id and conn.execute(select(t.institutions.c.institution_id).where(
                    t.institutions.c.tenant_id == actor.tenant_id,
                    t.institutions.c.institution_id == inst_id)).first() is None:
                raise ValidationFailed("That institution is not in your registry.", "institution_id")
            case_id = new_id("case")
            text_clean = sanitize_text(p.instruction_text, MAX_INSTRUCTION_CHARS).text
            received = date.fromisoformat(p.instruction_received_on) if p.instruction_received_on else None
            conn.execute(insert(t.cases).values(
                case_id=case_id, tenant_id=actor.tenant_id, created_by=actor.user_id, institution_id=inst_id,
                institution_query=(p.institution_query or None), instruction_text=text_clean,
                instruction_sha256=hashlib.sha256(text_clean.encode()).hexdigest(), instruction_received_on=received,
                paid_at=_local_midnight(p.paid_on, p.payment_tz, "paid_on"),
                due_at=_local_midnight(p.due_on, p.payment_tz, "due_on"), payment_tz=p.payment_tz, state="ACCEPTED",
                user_corrections=p.corrections, upload_ids=list(p.upload_ids), request_hash=rhash, created_at=now,
                updated_at=now))
            event_id = new_id("evt")
            traceparent = new_traceparent()
            envelope = {"event_id": event_id, "schema_version": 1, "type": "case.submitted",
                        "tenant_id": actor.tenant_id, "case_id": case_id, "occurred_at": now.isoformat(),
                        "traceparent": traceparent, "data": {"request_hash": rhash}}
            conn.execute(insert(t.outbox_events).values(
                event_id=event_id, tenant_id=actor.tenant_id, case_id=case_id, event_type="case.submitted",
                schema_version=1, payload=envelope, occurred_at=now, traceparent=traceparent, available_at=now))
            conn.execute(insert(t.idempotency_requests).values(tenant_id=actor.tenant_id, idempotency_key=key,
                                                               request_hash=rhash, case_id=case_id, created_at=now))
            append_audit(conn, actor.tenant_id, actor.user_id, "case.submitted", case_id, {"request_hash": rhash}, now)
        return SubmitResult(case_id, "ACCEPTED", rhash, False)

    # ------------------------------------------------------------- reads

    def get_case(self, actor: Actor, case_id: str) -> dict:
        with self.engine.connect() as conn:
            case = conn.execute(select(t.cases).where(t.cases.c.case_id == case_id,
                                                      t.cases.c.tenant_id == actor.tenant_id)).first()
            # Object-level authorization: payers see their own cases only. Same 404 either way (no enumeration).
            if case is None or (case.created_by != actor.user_id and not (actor.roles & READ_ALL_ROLES)):
                raise NotFound("Case not found.")
            job = conn.execute(select(t.jobs).where(t.jobs.c.case_id == case_id)).first()
            decisions = conn.execute(select(t.decisions).where(t.decisions.c.tenant_id == actor.tenant_id,
                                                                t.decisions.c.case_id == case_id)
                                     .order_by(t.decisions.c.created_at, t.decisions.c.assessment_kind)).all()
            run = conn.execute(select(t.inference_runs).where(t.inference_runs.c.tenant_id == actor.tenant_id,
                                                              t.inference_runs.c.case_id == case_id)
                               .order_by(t.inference_runs.c.started_at.desc()).limit(1)).first()
            reviews = conn.execute(select(t.reviews).where(t.reviews.c.tenant_id == actor.tenant_id,
                                                           t.reviews.c.case_id == case_id)
                                   .order_by(t.reviews.c.created_at)).all()
            inst = None
            if case.institution_id:
                inst = conn.execute(select(t.institutions).where(
                    t.institutions.c.institution_id == case.institution_id)).first()
        latest = decisions[-len({d.assessment_kind for d in decisions}):] if decisions else []
        return {
            "case_id": case.case_id, "state": case.state, "row_version": case.row_version,
            "institution_id": case.institution_id, "institution_query": case.institution_query,
            "institution": None if inst is None else {"name": inst.name, "timezone": inst.timezone,
                                                      "official_contact_url": inst.official_contact_url,
                                                      "synthetic": inst.synthetic},
            "instruction_text": case.instruction_text, "instruction_received_on": _iso(case.instruction_received_on),
            "paid_at": _iso(case.paid_at), "due_at": _iso(case.due_at), "payment_tz": case.payment_tz,
            "user_corrections": case.user_corrections, "synthetic": case.synthetic,
            "created_by": case.created_by, "created_at": _iso(case.created_at), "updated_at": _iso(case.updated_at),
            "job": None if job is None else {
                "job_id": job.job_id, "state": job.state, "attempts": job.attempts, "max_attempts": job.max_attempts,
                "run_after": _iso(job.run_after), "last_error": job.last_error},
            "inference": None if run is None else {
                "provider": run.provider, "model_id": run.model_id, "mode": run.mode, "latency_ms": run.latency_ms,
                "prompt_tokens": run.prompt_tokens, "completion_tokens": run.completion_tokens,
                "outcome": run.outcome, "started_at": _iso(run.started_at)},
            "claim": latest[0].claim if latest else None,
            "assessments": [{k: _iso(v) for k, v in d._mapping.items()} for d in latest],
            "reviews": [{"review_id": r.review_id, "reviewer_id": r.reviewer_id, "outcome": r.outcome,
                         "reason": r.reason, "created_at": _iso(r.created_at)} for r in reviews],
        }


    def list_cases(self, actor: Actor, *, needs_review: bool = False, limit: int = 50,
                   cursor: tuple[datetime, str] | None = None) -> list[dict]:
        """Newest first, cursor pagination on (created_at, case_id); uses ix_cases_tenant_id_created_at_case_id."""
        params: dict[str, Any] = {"tenant": actor.tenant_id, "limit": min(limit, 100)}
        where = ["c.tenant_id = :tenant"]
        if not (actor.roles & READ_ALL_ROLES):
            where.append("c.created_by = :user")
            params["user"] = actor.user_id
        if cursor is not None:
            where.append("(c.created_at, c.case_id) < (:cursor_at, :cursor_id)")
            params.update(cursor_at=cursor[0], cursor_id=cursor[1])
        if needs_review:
            where.append("EXISTS (SELECT 1 FROM decisions d WHERE d.tenant_id = c.tenant_id AND d.case_id = c.case_id "
                         "AND d.policy_decision IN ('REQUIRES_REVIEW', 'INSUFFICIENT_EVIDENCE')) "
                         "AND NOT EXISTS (SELECT 1 FROM reviews r WHERE r.tenant_id = c.tenant_id AND r.case_id = c.case_id)")
        sql = text(
            "SELECT c.case_id, c.state, c.created_at, c.created_by, c.institution_query, i.name AS institution_name, "
            "(SELECT d.policy_decision FROM decisions d WHERE d.tenant_id = c.tenant_id AND d.case_id = c.case_id "
            " ORDER BY (d.assessment_kind = 'NEXT_PAYMENT') DESC, d.created_at DESC LIMIT 1) AS decision, "
            "(SELECT count(*) FROM reviews r WHERE r.tenant_id = c.tenant_id AND r.case_id = c.case_id) AS reviews "
            "FROM cases c LEFT JOIN institutions i ON i.institution_id = c.institution_id "
            f"WHERE {' AND '.join(where)} ORDER BY c.created_at DESC, c.case_id DESC LIMIT :limit")
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(sql, params)]

    def institutions(self, actor: Actor) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(t.institutions.c.institution_id, t.institutions.c.name,
                                       t.institutions.c.country_code, t.institutions.c.timezone,
                                       t.institutions.c.synthetic)
                                .where(t.institutions.c.tenant_id == actor.tenant_id)
                                .order_by(t.institutions.c.name)).all()
        return [dict(r._mapping) for r in rows]


class _LeaseKeeper:
    """Background heartbeat while a job runs outside a transaction (e.g. during a model call)."""

    def __init__(self, queue: PgJobQueue, job: Job, owner: str):
        self.queue, self.job, self.owner = queue, job, owner
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.stop.wait(max(1.0, self.queue.lease_s / 3)):
            if not self.queue.heartbeat(self.job.job_id, self.owner):
                return

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()


class Worker:
    def __init__(self, engine: Engine, clock, queue: PgJobQueue, snapshots: PolicySnapshots,
                 extraction: ClaimExtraction):
        self.engine, self.clock, self.queue = engine, clock, queue
        self.snapshots, self.extraction = snapshots, extraction

    def relay(self, limit: int = 100) -> int:
        return self.queue.relay_outbox(limit)

    def run_once(self, owner: str) -> bool:
        job = self.queue.lease(owner)
        if job is None:
            return False
        self.process(job, owner)
        return True

    def process(self, job: Job, owner: str) -> str:
        with self.engine.connect() as conn:
            case = conn.execute(select(t.cases).where(t.cases.c.case_id == job.case_id,
                                                      t.cases.c.tenant_id == job.tenant_id)).one()
            names = conn.execute(select(t.institutions.c.institution_id, t.institutions.c.name,
                                        t.institutions.c.aliases)
                                 .where(t.institutions.c.tenant_id == job.tenant_id)).all()
        institution_id = case.institution_id
        hints = {"institution_name": next((n.name for n in names if n.institution_id == institution_id), None)}
        try:
            with _LeaseKeeper(self.queue, job, owner):
                snap = self.snapshots.load(job.tenant_id, institution_id)
                outcome = self.extraction.run(case.instruction_text, hints,
                                              final_attempt=job.attempts >= job.max_attempts)
        except TransientModelError as e:
            return self.queue.retry_or_dead_letter(job, owner, f"transient_model_error: {e}", e.retry_after)
        except Exception as e:   # a bug or permanent error: do not retry blindly
            self.queue.dead_letter(job, owner, f"{type(e).__name__}")
            return "DEAD_LETTER"

        claim = apply_corrections(outcome.claim, case.user_corrections or {})
        if institution_id is None:
            institution_id = _resolve(names, case.institution_query, claim)
            snap = self.snapshots.load(job.tenant_id, institution_id)
        injection = bool(detect_injection(case.instruction_text))
        for _ in range(3):
            ctx = EvaluationContext(job.tenant_id, snap.institution, snap.versions, snap.grants, self.clock(),
                                    injection_detected=injection, extra_limitations=outcome.limitations)
            assessments = assess_case(claim, ctx, case.paid_at, case.due_at)
            try:
                return self._commit(job, owner, case, institution_id, claim, assessments, snap, outcome)
            except EpochChanged:
                snap = self.snapshots.load(job.tenant_id, institution_id)
        return self.queue.retry_or_dead_letter(job, owner, "policy_epoch_unstable", None)

    def _commit(self, job: Job, owner, case, institution_id, claim: Claim, assessments: list[Assessment], snap,
                outcome) -> str:
        now = self.clock()
        with self.engine.begin() as conn:
            if not self.queue.holds_lease(conn, job.job_id, owner):
                return "lease_lost"
            first = conn.execute(text("INSERT INTO processed_events (consumer_name, event_id, processed_at) "
                                      "VALUES (:c, :e, :now) ON CONFLICT DO NOTHING RETURNING event_id"),
                                 {"c": CONSUMER, "e": job.source_event_id, "now": now}).first()
            if first is None:            # duplicate delivery: the decision already exists
                self.queue.complete(conn, job.job_id)
                return "duplicate"
            if institution_id and self.snapshots.epoch(conn, job.tenant_id, institution_id, lock=True) != snap.epoch:
                raise EpochChanged()
            rec = outcome.record
            conn.execute(insert(t.inference_runs).values(
                run_id=new_id("inf"), tenant_id=job.tenant_id, case_id=job.case_id, provider=rec.provider,
                model_id=rec.model_id, mode=rec.mode, started_at=now, latency_ms=rec.latency_ms,
                prompt_tokens=rec.prompt_tokens, completion_tokens=rec.completion_tokens,
                est_cost_usd=rec.est_cost_usd, outcome=rec.outcome, error_code=rec.error_code, attempt=job.attempts))
            claim_json = claim.as_dict()
            for a in assessments:
                conn.execute(insert(t.decisions).values(
                    decision_id=new_id("dec"), tenant_id=job.tenant_id, case_id=job.case_id,
                    assessment_kind=a.kind.value, target_time=a.target_time, policy_decision=a.decision.value,
                    evidence_level=a.evidence_level.value if a.evidence_level else None,
                    transaction_status=a.transaction_status.value, next_action=a.next_action.value,
                    findings=[{k: v for k, v in asdict(f).items()} for f in a.findings],
                    limitations=[lim.value for lim in a.limitations],
                    applied_version_ids=list(a.applied_version_ids),
                    considered_version_ids=list(a.considered_version_ids), claim=claim_json,
                    evidence_snapshot=snap.raw, rule_version=a.rule_version, model_version=outcome.model_version,
                    request_hash=case.request_hash, policy_epoch=snap.epoch, created_at=now))
            set_case_state(conn, job.case_id, "COMPLETED", now, institution_id=institution_id)
            self.queue.complete(conn, job.job_id)
            append_audit(conn, job.tenant_id, f"worker:{owner}", "case.decided", job.case_id,
                         {"decisions": [a.decision.value for a in assessments], "model": outcome.model_version}, now)
        return "COMPLETED"


def _resolve(names, query: str | None, claim: Claim) -> str | None:
    """Exact normalized match on name or alias only. Fuzzy similarity never decides identity."""
    wanted = {normalize.name(v) for v in (query, claim.institution_name.value if claim.institution_name else None) if v}
    for n in names:
        if wanted & {normalize.name(x) for x in [n.name, *(n.aliases or [])]}:
            return n.institution_id
    return None


class Reviews:
    def __init__(self, engine: Engine, clock, experience_enabled: bool):
        self.engine, self.clock, self.experience_enabled = engine, clock, experience_enabled

    def submit(self, actor: Actor, case_id: str, outcome: str, reason: str, expected_row_version: int) -> str:
        now = self.clock()
        with self.engine.begin() as conn:
            case = conn.execute(select(t.cases).where(t.cases.c.case_id == case_id,
                                                      t.cases.c.tenant_id == actor.tenant_id)).first()
            if case is None:
                raise NotFound("Case not found.")
            if "reviewer" not in actor.roles:
                raise Forbidden("Only institution reviewers can record a review.")
            if outcome not in REVIEW_OUTCOMES:
                raise ValidationFailed("Choose a review outcome.", "outcome")
            if len((reason or "").strip()) < 10:
                raise ValidationFailed("Give a reason of at least 10 characters.", "reason")
            if case.state != "COMPLETED":
                raise ValidationFailed("The check has not finished yet.", "case")
            res = conn.execute(update(t.cases).where(t.cases.c.case_id == case_id,
                                                     t.cases.c.row_version == expected_row_version)
                               .values(row_version=t.cases.c.row_version + 1, updated_at=now))
            if res.rowcount != 1:
                raise ConcurrencyConflict("The case changed since you opened it. Reload and review again.")
            review_id = new_id("rev")
            conn.execute(insert(t.reviews).values(review_id=review_id, tenant_id=actor.tenant_id, case_id=case_id,
                                                  reviewer_id=actor.user_id, outcome=outcome, reason=reason.strip(),
                                                  case_row_version=expected_row_version + 1, created_at=now))
            if self.experience_enabled and outcome == "CONFIRMED":
                dec = conn.execute(select(t.decisions).where(t.decisions.c.case_id == case_id)
                                   .order_by(t.decisions.c.created_at.desc()).limit(1)).first()
                if dec is not None and case.institution_id:
                    conn.execute(insert(t.experience_records).values(
                        record_id=new_id("exp"), tenant_id=actor.tenant_id, case_id=case_id, review_id=review_id,
                        institution_id=case.institution_id, version_ids=dec.applied_version_ids,
                        lesson=f"{dec.policy_decision}: " + ", ".join(f["reason"] for f in dec.findings),
                        created_at=now))
            append_audit(conn, actor.tenant_id, actor.user_id, "case.reviewed", case_id,
                         {"outcome": outcome, "review_id": review_id}, now)
        return review_id


class Policies:
    def __init__(self, engine: Engine, clock):
        self.engine, self.clock = engine, clock

    def row_version(self, version_id: str) -> int:
        with self.engine.connect() as conn:
            return conn.execute(select(t.policy_versions.c.row_version)
                                .where(t.policy_versions.c.version_id == version_id)).scalar_one()

    def _guard(self, conn, actor: Actor, version_id: str):
        if "policy_admin" not in actor.roles or not actor.mfa:
            raise Forbidden("Policy changes need the policy administrator role and multi-factor sign-in.")
        row = conn.execute(select(t.policy_versions).where(t.policy_versions.c.version_id == version_id,
                                                           t.policy_versions.c.tenant_id == actor.tenant_id)).first()
        if row is None:
            raise NotFound("Policy version not found.")
        return row

    def _invalidate(self, conn, tenant_id: str, institution_id: str, version_id: str, everything: bool) -> None:
        conn.execute(update(t.institutions).where(t.institutions.c.institution_id == institution_id)
                     .values(policy_epoch=t.institutions.c.policy_epoch + 1))   # new cache key epoch
        cond = "TRUE" if everything else "d.applied_version_ids ? :v"
        conn.execute(text(f"UPDATE decisions d SET needs_reevaluation = true FROM cases c WHERE c.case_id = d.case_id "
                          f"AND c.tenant_id = :t AND c.institution_id = :i AND ({cond})"),
                     {"t": tenant_id, "i": institution_id, "v": version_id})
        conn.execute(text("UPDATE experience_records SET status = 'INVALIDATED' WHERE tenant_id = :t "
                          "AND version_ids ? :v AND status = 'ACTIVE'"), {"t": tenant_id, "v": version_id})

    def approve(self, actor: Actor, version_id: str, expected_row_version: int) -> None:
        now = self.clock()
        with self.engine.begin() as conn:
            row = self._guard(conn, actor, version_id)
            if row.discovered_by == actor.user_id:
                raise Forbidden("The account that discovered a policy cannot approve it.")
            if row.approval_status != "DISCOVERED":
                raise ValidationFailed("Only discovered versions can be approved.", "approval_status")
            res = conn.execute(update(t.policy_versions).where(t.policy_versions.c.version_id == version_id,
                                                               t.policy_versions.c.row_version == expected_row_version)
                               .values(approval_status="APPROVED", approved_by=actor.user_id, approved_at=now,
                                       row_version=t.policy_versions.c.row_version + 1))
            if res.rowcount != 1:
                raise ConcurrencyConflict("The policy version changed. Reload before approving.")
            self._invalidate(conn, actor.tenant_id, row.institution_id, version_id, everything=True)
            append_audit(conn, actor.tenant_id, actor.user_id, "policy.approved", version_id, {}, now)

    def revoke(self, actor: Actor, version_id: str, reason: str, expected_row_version: int) -> None:
        now = self.clock()
        with self.engine.begin() as conn:
            row = self._guard(conn, actor, version_id)
            res = conn.execute(update(t.policy_versions).where(t.policy_versions.c.version_id == version_id,
                                                               t.policy_versions.c.row_version == expected_row_version)
                               .values(revoked_at=now, row_version=t.policy_versions.c.row_version + 1))
            if res.rowcount != 1:
                raise ConcurrencyConflict("The policy version changed. Reload before revoking.")
            self._invalidate(conn, actor.tenant_id, row.institution_id, version_id, everything=False)
            append_audit(conn, actor.tenant_id, actor.user_id, "policy.revoked", version_id, {"reason": reason}, now)


class Ops:
    def __init__(self, engine: Engine, clock, queue: PgJobQueue):
        self.engine, self.clock, self.queue = engine, clock, queue

    def replay(self, actor: Actor, job_id: str) -> None:
        if "ops_admin" not in actor.roles:
            raise Forbidden("Replaying dead letters needs the operations administrator role.")
        with self.engine.begin() as conn:
            owner = conn.execute(select(t.jobs.c.tenant_id).where(t.jobs.c.job_id == job_id)).scalar_one_or_none()
            if owner != actor.tenant_id:
                raise NotFound("Job not found.")
            try:
                case_id = self.queue.replay(conn, job_id)
            except LookupError:
                raise ValidationFailed("Only dead-lettered jobs can be replayed.", "job") from None
            append_audit(conn, actor.tenant_id, actor.user_id, "job.replay", job_id, {"case_id": case_id},
                         self.clock())


@dataclass
class Container:
    engine: Engine
    settings: PGSettings
    intake: IntakeService
    worker: Worker
    queue: PgJobQueue
    reviews: Reviews
    policies: Policies
    ops: Ops
    snapshots: PolicySnapshots
    extraction: ClaimExtraction
    budget: PgBudgetLedger | None

    def cache_epoch(self, tenant_id: str, institution_id: str) -> int | None:
        with self.engine.connect() as conn:
            return self.snapshots.epoch(conn, tenant_id, institution_id)


def build_container(engine: Engine, settings: PGSettings, clock, *, paid_model: PaidClaimModel | None = None,
                    rules_extractor: ClaimExtractor | None = None, budget_override: tuple[float, int] | None = None,
                    experience_enabled: bool = False, cache: SnapshotCache | None = None, rng=None) -> Container:
    queue = PgJobQueue(engine, clock, settings.lease_seconds, settings.max_attempts, settings.job_deadline_seconds,
                       rng=rng)
    snapshots = PolicySnapshots(engine, cache if cache is not None else InMemoryCache())
    if paid_model is None and settings.paid_inference_enabled:
        from policyguard.infra.nebius import NebiusClaimModel
        paid_model = NebiusClaimModel.from_settings(settings)
    budget = None
    if paid_model is not None:
        budget = PgBudgetLedger(engine)
        if budget_override is not None:
            budget.configure(Decimal(str(budget_override[0])), budget_override[1])
        elif settings.budget_usd:
            budget.configure(settings.budget_usd, settings.max_paid_calls)

    def estimate(text_: str) -> Decimal:   # worst case: every character a token, full output allowance
        return (Decimal(len(text_) + 1500) * settings.price_in_per_mtok
                + Decimal(settings.max_output_tokens) * settings.price_out_per_mtok) / Decimal(1_000_000)

    def cost(usage: Usage) -> Decimal:
        return (Decimal(usage.prompt_tokens) * settings.price_in_per_mtok
                + Decimal(usage.completion_tokens) * settings.price_out_per_mtok) / Decimal(1_000_000)

    extraction = ClaimExtraction(rules=rules_extractor or RulesExtractor(), paid_model=paid_model, budget=budget,
                                 estimate_usd=estimate, cost_usd=cost)
    return Container(engine, settings, IntakeService(engine, clock),
                     Worker(engine, clock, queue, snapshots, extraction), queue,
                     Reviews(engine, clock, experience_enabled), Policies(engine, clock), Ops(engine, clock, queue),
                     snapshots, extraction, budget)
