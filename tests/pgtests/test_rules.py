"""Deterministic decisions. Numbers in test names refer to the mandatory cases in the brief."""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from policyguard.domain.model import (
    AssessmentKind,
    EvidenceLevel,
    Limitation,
    NextAction,
    PolicyDecision,
    Reason,
    TransactionStatus,
)
from policyguard.domain.rules import RULE_VERSION, assess_case, evaluate

from .factories import claim, ctx, grant, utc, version

NEXT = AssessmentKind.NEXT_PAYMENT


def reasons(a):
    return {f.reason for f in a.findings}


def test_01_matching_instruction_is_consistent_but_not_settlement():
    a = evaluate(claim(), ctx([version()]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.CONSISTENT
    assert a.evidence_level is EvidenceLevel.INSTITUTION_ATTESTED
    assert a.transaction_status is TransactionStatus.UNKNOWN
    assert a.next_action is NextAction.PAY_ONLY_THROUGH_OFFICIAL_CHANNEL
    assert Limitation.NOT_A_SETTLEMENT_CHECK in a.limitations
    assert a.applied_version_ids == ("v1",)
    assert a.rule_version == RULE_VERSION


def test_account_and_payee_are_normalized_before_comparison():
    a = evaluate(claim(account="gb29-synt-6016-1331-9268-19", payee="ASTER BAY UNIVERSITY."), ctx([version()]),
                 NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.CONSISTENT


def test_02_account_conflict():
    a = evaluate(claim(account="GB11 SYNT 0000 0000 9999 99"), ctx([version()]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.CONFLICT
    assert Reason.ACCOUNT_MISMATCH in reasons(a)
    assert a.next_action is NextAction.DO_NOT_PAY_CONTACT_INSTITUTION


def test_payee_and_currency_conflicts_are_reported_per_field():
    a = evaluate(claim(payee="Northbridge Education Services Ltd", currency="USD"), ctx([version()]), NEXT,
                 utc(2026, 11, 15))
    assert a.decision is PolicyDecision.CONFLICT
    assert {Reason.PAYEE_MISMATCH, Reason.CURRENCY_MISMATCH} <= reasons(a)


def test_channel_not_allowed_is_a_conflict():
    a = evaluate(claim(channel="crypto_wallet"), ctx([version()]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.CONFLICT and Reason.CHANNEL_NOT_ALLOWED in reasons(a)


def test_03_missing_payment_date_is_insufficient_not_guessed():
    a = evaluate(claim(), ctx([version()]), NEXT, None)
    assert a.decision is PolicyDecision.INSUFFICIENT_EVIDENCE
    assert Reason.DATE_UNKNOWN in reasons(a)
    assert a.next_action is NextAction.PROVIDE_PAYMENT_DATE


def test_03_unknown_policy_validity_is_insufficient():
    a = evaluate(claim(), ctx([version(valid_from=None)]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.INSUFFICIENT_EVIDENCE and Reason.VALIDITY_UNKNOWN in reasons(a)


def test_03_no_policy_at_date():
    a = evaluate(claim(), ctx([version(valid_from=utc(2027, 1, 1))]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.INSUFFICIENT_EVIDENCE and Reason.NO_POLICY_AT_DATE in reasons(a)


def test_04_old_policy_is_valid_historically_but_not_for_next_payment():
    old_account = "GB29 SYNT 6016 1331 9268 19"
    v1 = version("v1", account=old_account, valid_from=utc(2026, 1, 1), valid_to=utc(2026, 9, 1))
    v2 = version("v2", account="GB94 SYNT 4000 0000 5555 01", valid_from=utc(2026, 9, 1),
                 supersedes_version_id="v1", recorded_at=utc(2026, 8, 20))
    hist, nxt = assess_case(claim(account=old_account), ctx([v1, v2]), paid_at=utc(2026, 8, 15),
                            due_at=utc(2026, 11, 15))
    assert hist.kind is AssessmentKind.HISTORICAL and hist.decision is PolicyDecision.CONSISTENT
    assert hist.applied_version_ids == ("v1",) and Limitation.HISTORICAL_ONLY in hist.limitations
    assert nxt.kind is NEXT and nxt.decision is PolicyDecision.CONFLICT
    assert nxt.applied_version_ids == ("v2",)
    assert {Reason.ACCOUNT_MISMATCH, Reason.MATCHES_SUPERSEDED_POLICY} <= reasons(nxt)


def test_05_conflicting_authoritative_sources_require_review_and_latest_is_not_picked():
    a1 = version("v1", policy_id="pol-web")
    a2 = version("v9", policy_id="pol-handbook", account="GB55 SYNT 1111 2222 3333 44", recorded_at=utc(2026, 10, 1))
    a = evaluate(claim(), ctx([a1, a2]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.REQUIRES_REVIEW
    assert Reason.SOURCE_CONFLICT in reasons(a)
    assert set(a.applied_version_ids) == {"v1", "v9"}
    assert a.next_action is NextAction.WAIT_FOR_INSTITUTION_REVIEW


def test_agreeing_sources_do_not_create_a_conflict():
    a = evaluate(claim(), ctx([version("v1", policy_id="pol-web"), version("v2", policy_id="pol-handbook")]), NEXT,
                 utc(2026, 11, 15))
    assert a.decision is PolicyDecision.CONSISTENT


def test_unauthorized_issuer_gives_insufficient_evidence():
    v = version(issuer_id="partner-agency", evidence_level=EvidenceLevel.PUBLIC_SOURCE)
    a = evaluate(claim(), ctx([v]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.INSUFFICIENT_EVIDENCE
    assert Reason.ISSUER_NOT_AUTHORIZED in reasons(a)
    assert a.evidence_level is EvidenceLevel.PUBLIC_SOURCE
    assert a.next_action is NextAction.REQUEST_INSTITUTION_CONFIRMATION


def test_authority_must_be_valid_at_target_time():
    g = grant(valid_from=utc(2026, 12, 1))
    a = evaluate(claim(), ctx([version()], grants=[g]), NEXT, utc(2026, 11, 15))
    assert Reason.ISSUER_NOT_AUTHORIZED in reasons(a)


def test_revoked_grant_is_not_authority():
    g = grant(revoked_at=utc(2026, 10, 1))
    a = evaluate(claim(), ctx([version()], grants=[g]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.INSUFFICIENT_EVIDENCE


def test_unknown_institution():
    a = evaluate(claim(), ctx([], inst=None), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.INSUFFICIENT_EVIDENCE and Reason.UNKNOWN_INSTITUTION in reasons(a)


def test_missing_account_in_instruction_is_incomplete():
    a = evaluate(claim(account=None), ctx([version()]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.INSUFFICIENT_EVIDENCE and Reason.CLAIM_INCOMPLETE in reasons(a)


def test_09_injection_escalates_even_when_fields_match():
    a = evaluate(claim(), ctx([version()], injection_detected=True), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.REQUIRES_REVIEW and Reason.PROMPT_INJECTION_DETECTED in reasons(a)


def test_stale_source_requires_review():
    a = evaluate(claim(), ctx([version(freshness_deadline=utc(2026, 10, 1))]), NEXT, utc(2026, 11, 15))
    assert a.decision is PolicyDecision.REQUIRES_REVIEW and Reason.SOURCE_STALE in reasons(a)


def test_open_ended_policy_carries_end_date_limitation():
    a = evaluate(claim(), ctx([version(valid_to=None)]), NEXT, utc(2026, 11, 15))
    assert Limitation.END_DATE_UNKNOWN in a.limitations


def test_case_without_dates_gives_one_next_payment_assessment():
    (only,) = assess_case(claim(), ctx([version()]), paid_at=None, due_at=None)
    assert only.kind is NEXT and Reason.DATE_UNKNOWN in reasons(only)


@given(account=st.text(max_size=30), payee=st.text(max_size=40), currency=st.sampled_from(["GBP", "USD", "", "XXX"]),
       injection=st.booleans())
def test_rules_never_claim_settlement(account, payee, currency, injection):
    a = evaluate(claim(account=account or None, payee=payee or None, currency=currency or None),
                 ctx([version()], injection_detected=injection), NEXT, utc(2026, 11, 15))
    assert a.transaction_status is TransactionStatus.UNKNOWN
    assert a.decision in set(PolicyDecision)


def test_freshness_deadline_does_not_apply_to_versions_that_already_ended():
    ended = version("v1", valid_from=utc(2025, 8, 1), valid_to=utc(2026, 9, 1), freshness_deadline=utc(2026, 9, 1))
    a = evaluate(claim(), ctx([ended]), AssessmentKind.HISTORICAL, utc(2026, 8, 14))
    assert a.decision is PolicyDecision.CONSISTENT and Reason.SOURCE_STALE not in reasons(a)
