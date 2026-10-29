"""Durable intake, outbox relay, worker leases, retries and dead letters (mandatory cases 6, 7, 11-14, 17, 19)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, func, select, update

from policyguard.application.errors import (
    ConcurrencyConflict,
    DurableWriteUnavailable,
    Forbidden,
    IdempotencyConflict,
    NotFound,
    TransientModelError,
)
from policyguard.application.extraction import RulesExtractor
from policyguard.application.service import Actor, CaseInput, build_container
from policyguard.domain.model import Limitation
from policyguard.infra import tables as t
from policyguard.seed import DISCOVERED_VERSION_ID, SAMPLES, TENANT, load_demo

PAYER = Actor("pg_payer", TENANT, frozenset({"payer"}))
REVIEWER = Actor("pg_reviewer", TENANT, frozenset({"reviewer"}))
ADMIN = Actor("pg_admin", TENANT, frozenset({"policy_admin", "ops_admin"}), mfa=True)
OTHER_TENANT = Actor("intruder", "tenant-other", frozenset({"payer", "reviewer"}))


def sample(key: str, **kw) -> CaseInput:
    return CaseInput(**{**SAMPLES[key]["input"], **kw})


@pytest.fixture
def c(db, clock, pg_settings):
    load_demo(db, clock())
    return build_container(db, pg_settings, clock)


def count(db, table, **where) -> int:
    q = select(func.count()).select_from(table)
    for k, v in where.items():
        q = q.where(table.c[k] == v)
    with db.connect() as conn:
        return conn.execute(q).scalar_one()


def finish(c, owner="w1") -> None:
    c.worker.relay()
    while c.worker.run_once(owner):
        pass


def test_submit_commits_case_and_outbox_together(c, db):
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    assert r.state == "ACCEPTED" and not r.replayed
    with db.connect() as conn:
        ev = conn.execute(select(t.outbox_events).where(t.outbox_events.c.case_id == r.case_id)).one()
    assert ev.status == "PENDING" and ev.schema_version == 1 and ev.event_type == "case.submitted"
    assert set(ev.payload) >= {"event_id", "schema_version", "tenant_id", "case_id", "occurred_at", "traceparent"}
    assert "instruction_text" not in ev.payload          # events carry references, not payment data


def test_same_key_same_payload_returns_same_case(c):
    a = c.intake.submit(PAYER, "key-1", sample("conflict"))
    b = c.intake.submit(PAYER, "key-1", sample("conflict"))
    assert a.case_id == b.case_id and b.replayed


def test_same_key_different_payload_is_rejected(c):
    c.intake.submit(PAYER, "key-1", sample("conflict"))
    with pytest.raises(IdempotencyConflict):
        c.intake.submit(PAYER, "key-1", sample("policy_change"))


def test_12_concurrent_requests_with_one_key_create_one_case(c, db):
    with ThreadPoolExecutor(8) as pool:
        ids = set(pool.map(lambda _: c.intake.submit(PAYER, "key-race", sample("conflict")).case_id, range(8)))
    assert len(ids) == 1 and count(db, t.cases) == 1 and count(db, t.outbox_events) == 1


def test_16_storage_failure_is_not_acknowledged(db, clock, pg_settings):
    dead = create_engine("postgresql+psycopg://policyguard@127.0.0.1:1/none", pool_pre_ping=False)
    c = build_container(dead, pg_settings, clock)
    with pytest.raises(DurableWriteUnavailable):
        c.intake.submit(PAYER, "key-1", sample("conflict"))


def test_end_to_end_decision_is_stored_with_snapshot(c):
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    finish(c)
    view = c.intake.get_case(PAYER, r.case_id)
    assert view["state"] == "COMPLETED"
    (d,) = view["assessments"]
    assert d["policy_decision"] == "CONFLICT" and d["transaction_status"] == "UNKNOWN"
    assert d["rule_version"] and d["model_version"].startswith("rules:") and d["request_hash"] == r.request_hash
    snapshot_ids = {v["version_id"] for v in d["evidence_snapshot"]["versions"]}
    assert set(d["applied_version_ids"]) <= snapshot_ids
    assert view["inference"]["mode"] == "rules"


def test_04_policy_change_sample_gives_two_assessments(c):
    r = c.intake.submit(PAYER, "key-1", sample("policy_change"))
    finish(c)
    hist, nxt = c.intake.get_case(PAYER, r.case_id)["assessments"]
    assert (hist["assessment_kind"], hist["policy_decision"]) == ("HISTORICAL", "CONSISTENT")
    assert (nxt["assessment_kind"], nxt["policy_decision"]) == ("NEXT_PAYMENT", "CONFLICT")


def test_insufficient_evidence_sample(c):
    r = c.intake.submit(PAYER, "key-1", sample("insufficient"))
    finish(c)
    (d,) = c.intake.get_case(PAYER, r.case_id)["assessments"]
    assert d["policy_decision"] == "INSUFFICIENT_EVIDENCE"
    assert c.intake.get_case(PAYER, r.case_id)["state"] == "COMPLETED"   # completed even when evidence is missing


def test_13_duplicate_events_are_processed_once(c, db):
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    c.worker.relay()
    with db.begin() as conn:   # redeliver the same event
        conn.execute(update(t.outbox_events).values(status="PENDING"))
    c.worker.relay()
    assert count(db, t.jobs) == 1
    finish(c)
    job_id = c.intake.get_case(PAYER, r.case_id)["job"]["job_id"]
    with db.begin() as conn:   # a stale redelivery after completion
        conn.execute(update(t.jobs).where(t.jobs.c.job_id == job_id).values(state="QUEUED"))
    finish(c)
    assert count(db, t.decisions, case_id=r.case_id) == 1


def test_14_worker_crash_before_ack_is_recovered_without_duplicates(c, db, clock):
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    c.worker.relay()
    assert c.queue.lease("crashed-worker") is not None     # leased, then the worker dies
    assert c.worker.run_once("w2") is False                  # lease still valid
    clock.advance(seconds=31)
    assert c.worker.run_once("w2") is True
    assert c.intake.get_case(PAYER, r.case_id)["state"] == "COMPLETED"
    assert count(db, t.decisions, case_id=r.case_id) == 1


def test_lost_lease_cannot_commit(c, db, clock):
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    c.worker.relay()
    stale = c.queue.lease("w1")
    clock.advance(seconds=31)
    assert c.worker.run_once("w2") is True
    c.worker.process(stale, "w1")                             # late worker finishes: must not write
    assert count(db, t.decisions, case_id=r.case_id) == 1


class FlakyModel:
    """A paid-model stand-in that fails with a transient provider error."""
    model_id = "test/flaky"
    mode = "mock"

    def __init__(self, failures: int, retry_after: float | None = 5.0):
        self.failures, self.retry_after, self.calls = failures, retry_after, 0

    def extract(self, text, hints):
        self.calls += 1
        if self.calls <= self.failures:
            raise TransientModelError("provider 429", retry_after=self.retry_after)
        return RulesExtractor().extract(text, hints)


def test_15_transient_errors_retry_with_backoff_then_degrade_safely(db, clock, pg_settings):
    load_demo(db, clock())
    c = build_container(db, pg_settings, clock, paid_model=FlakyModel(failures=10), budget_override=(1, 10))
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    c.worker.relay()
    assert c.worker.run_once("w1")
    view = c.intake.get_case(PAYER, r.case_id)
    assert view["state"] == "RETRY_WAIT" and view["job"]["attempts"] == 1
    assert view["job"]["run_after"] >= clock() .isoformat()[:19]
    for _ in range(3):
        clock.advance(minutes=5)
        c.worker.run_once("w1")
    view = c.intake.get_case(PAYER, r.case_id)
    assert view["state"] == "COMPLETED"                       # a provider outage is not a fraud verdict
    assert Limitation.MODEL_UNAVAILABLE in view["assessments"][0]["limitations"]


class BrokenExtractor:
    def extract(self, text, hints):
        raise RuntimeError("unexpected bug")


def test_permanent_error_dead_letters_and_replay_is_authorized_and_audited(db, clock, pg_settings):
    load_demo(db, clock())
    c = build_container(db, pg_settings, clock, rules_extractor=BrokenExtractor())
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    finish(c)
    view = c.intake.get_case(PAYER, r.case_id)
    assert view["state"] == "FAILED" and view["job"]["state"] == "DEAD_LETTER" and view["job"]["attempts"] == 1
    with pytest.raises(Forbidden):
        c.ops.replay(PAYER, view["job"]["job_id"])
    c.ops.replay(ADMIN, view["job"]["job_id"])
    assert c.intake.get_case(PAYER, r.case_id)["job"]["state"] == "QUEUED"
    assert count(db, t.audit_entries, action="job.replay") == 1


def test_07_policy_change_during_processing_is_detected(db, clock, pg_settings):
    load_demo(db, clock())

    class EpochBumpingExtractor(RulesExtractor):
        def extract(self, text, hints):
            with db.begin() as conn:   # an approval lands while the worker is busy
                conn.execute(update(t.institutions).values(policy_epoch=t.institutions.c.policy_epoch + 1))
            return super().extract(text, hints)

    c = build_container(db, pg_settings, clock, rules_extractor=EpochBumpingExtractor())
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    finish(c)
    view = c.intake.get_case(PAYER, r.case_id)
    with db.connect() as conn:
        epoch = conn.execute(select(t.institutions.c.policy_epoch)
                             .where(t.institutions.c.institution_id == view["institution_id"])).scalar_one()
    assert view["assessments"][0]["policy_epoch"] == epoch


def test_06_approval_and_revocation_invalidate_decisions_cache_and_experience(db, clock, pg_settings):
    load_demo(db, clock())
    c = build_container(db, pg_settings, clock, experience_enabled=True)
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    finish(c)
    view = c.intake.get_case(REVIEWER, r.case_id)
    c.reviews.submit(REVIEWER, r.case_id, "CONFIRMED", "Bursar confirmed the account is not theirs.",
                     view["row_version"])
    assert count(db, t.experience_records, status="ACTIVE") == 1
    epoch_before = c.cache_epoch(TENANT, view["institution_id"])
    version_id = view["assessments"][0]["applied_version_ids"][0]
    c.policies.revoke(ADMIN, version_id, "Account closed", c.policies.row_version(version_id))
    assert c.cache_epoch(TENANT, view["institution_id"]) == epoch_before + 1
    assert count(db, t.experience_records, status="INVALIDATED") == 1
    assert c.intake.get_case(PAYER, r.case_id)["assessments"][0]["needs_reevaluation"] is True


def test_11_other_tenant_cannot_read_or_review(c):
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    with pytest.raises(NotFound):
        c.intake.get_case(OTHER_TENANT, r.case_id)
    with pytest.raises(NotFound):
        c.reviews.submit(OTHER_TENANT, r.case_id, "CONFIRMED", "x" * 12, 1)


class CountingModel:
    model_id = "test/counting"
    mode = "mock"

    def __init__(self):
        self.calls = 0

    def extract(self, text, hints):
        self.calls += 1
        return RulesExtractor().extract(text, hints)


def test_17_exhausted_budget_skips_paid_inference(db, clock, pg_settings):
    load_demo(db, clock())
    model = CountingModel()
    c = build_container(db, pg_settings, clock, paid_model=model, budget_override=(1, 1))
    first = c.intake.submit(PAYER, "key-1", sample("conflict"))
    second = c.intake.submit(PAYER, "key-2", sample("policy_change"))
    finish(c)
    assert model.calls == 1                      # job order is not guaranteed, so check the pair
    views = sorted((c.intake.get_case(PAYER, r.case_id) for r in (first, second)), key=lambda v: v["inference"]["mode"])
    assert [v["inference"]["mode"] for v in views] == ["mock", "rules"]
    assert views[1]["inference"]["outcome"] == "budget_exhausted"
    assert Limitation.PAID_INFERENCE_DISABLED in views[1]["assessments"][0]["limitations"]


def test_19_only_authorized_reviewers_create_experience(db, clock, pg_settings):
    load_demo(db, clock())
    c = build_container(db, pg_settings, clock, experience_enabled=True)
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    finish(c)
    with pytest.raises(Forbidden):
        c.reviews.submit(PAYER, r.case_id, "CONFIRMED", "I think it is fine really", 1)
    assert count(db, t.experience_records) == 0


def test_review_requires_current_row_version(c):
    r = c.intake.submit(PAYER, "key-1", sample("conflict"))
    finish(c)
    with pytest.raises(ConcurrencyConflict):
        c.reviews.submit(REVIEWER, r.case_id, "CONFIRMED", "Confirmed with the bursar office.", 1)


def test_policy_approval_needs_admin_mfa_and_a_second_person(c, db):
    vid = DISCOVERED_VERSION_ID
    rv = c.policies.row_version(vid)
    with pytest.raises(Forbidden):
        c.policies.approve(REVIEWER, vid, rv)
    with pytest.raises(Forbidden):
        c.policies.approve(Actor("pg_admin", TENANT, frozenset({"policy_admin"}), mfa=False), vid, rv)
    with pytest.raises(Forbidden):   # discovery cannot approve itself
        c.policies.approve(Actor("ingestion-bot", TENANT, frozenset({"policy_admin"}), mfa=True), vid, rv)
    with pytest.raises(ConcurrencyConflict):
        c.policies.approve(ADMIN, vid, rv + 5)
    c.policies.approve(ADMIN, vid, rv)
    assert c.policies.row_version(vid) == rv + 1
