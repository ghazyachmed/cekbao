"""Deterministic decision rules. The model never decides; it only proposes claim fields.

Order of checks (first failing check decides):
institution known -> target date known -> any policy -> issuer authorized at the date
-> a version valid at the date -> authoritative sources agree -> instruction complete
-> field comparison.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from . import normalize
from .model import (
    EVIDENCE_RANK,
    Assessment,
    AssessmentKind,
    AuthorityGrant,
    Claim,
    EvaluationContext,
    EvidenceLevel,
    Finding,
    Limitation,
    NextAction,
    PolicyDecision,
    PolicyVersion,
    Reason,
    TransactionStatus,
)
from .temporal import HalfOpenIntervalSelector, TemporalSelector

RULE_VERSION = "pg-rules-2026.10.1"
DEFAULT_SELECTOR = HalfOpenIntervalSelector()

_NEXT_ACTION = {
    PolicyDecision.CONSISTENT: NextAction.PAY_ONLY_THROUGH_OFFICIAL_CHANNEL,
    PolicyDecision.CONFLICT: NextAction.DO_NOT_PAY_CONTACT_INSTITUTION,
    PolicyDecision.INSUFFICIENT_EVIDENCE: NextAction.REQUEST_INSTITUTION_CONFIRMATION,
    PolicyDecision.REQUIRES_REVIEW: NextAction.WAIT_FOR_INSTITUTION_REVIEW,
}


def _grant_for(v: PolicyVersion, grants: Iterable[AuthorityGrant], t: datetime, as_of: datetime) -> AuthorityGrant | None:
    for g in grants:
        if (g.tenant_id == v.tenant_id and g.institution_id == v.institution_id and g.issuer_id == v.issuer_id
                and g.authority_scope == v.authority_scope and g.recorded_at <= as_of
                and (g.revoked_at is None or g.revoked_at > as_of)
                and g.valid_from is not None and g.valid_from <= t and (g.valid_to is None or t < g.valid_to)):
            return g
    return None


def _payee_key(v: PolicyVersion) -> tuple[str, str, str]:
    return (normalize.account(v.payee.account_number), normalize.name(v.payee.payee_name),
            normalize.code(v.payee.currency))


def _weakest(levels: Iterable[EvidenceLevel]) -> EvidenceLevel | None:
    ordered = sorted(levels, key=EVIDENCE_RANK.__getitem__)
    return ordered[0] if ordered else None


class _Builder:
    def __init__(self, kind: AssessmentKind, t: datetime | None, ctx: EvaluationContext):
        self.kind, self.t = kind, t
        self.limitations: list[Limitation] = list(ctx.extra_limitations) + [Limitation.NOT_A_SETTLEMENT_CHECK]

    def done(self, decision: PolicyDecision, findings: list[Finding], evidence: EvidenceLevel | None,
             applied: Iterable[PolicyVersion] = (), considered: Iterable[PolicyVersion] = (),
             next_action: NextAction | None = None) -> Assessment:
        applied, considered = tuple(applied), tuple(considered)
        if any(v.synthetic for v in applied + considered):
            self.limitations.append(Limitation.SYNTHETIC_DATA)
        return Assessment(
            kind=self.kind, target_time=self.t, decision=decision, evidence_level=evidence,
            transaction_status=TransactionStatus.UNKNOWN,  # policy rules never establish settlement
            next_action=next_action or _NEXT_ACTION[decision], findings=tuple(findings),
            limitations=tuple(dict.fromkeys(self.limitations)),
            applied_version_ids=tuple(v.version_id for v in applied),
            considered_version_ids=tuple(dict.fromkeys(v.version_id for v in considered + applied)),
            rule_version=RULE_VERSION)


def evaluate(claim: Claim, ctx: EvaluationContext, kind: AssessmentKind, t: datetime | None,
             selector: TemporalSelector = DEFAULT_SELECTOR) -> Assessment:
    b = _Builder(kind, t, ctx)
    INSUFFICIENT = PolicyDecision.INSUFFICIENT_EVIDENCE
    inst = ctx.institution
    if inst is None:
        return b.done(INSUFFICIENT, [Finding(Reason.UNKNOWN_INSTITUTION, "institution_name")], None)
    if t is None:
        return b.done(INSUFFICIENT, [Finding(Reason.DATE_UNKNOWN)], None, next_action=NextAction.PROVIDE_PAYMENT_DATE)

    versions = [v for v in ctx.versions if v.tenant_id == ctx.tenant_id and v.institution_id == inst.institution_id]
    if not versions:
        return b.done(INSUFFICIENT, [Finding(Reason.NO_POLICY_FOUND)], None)

    grants = {v.version_id: _grant_for(v, ctx.grants, t, ctx.as_of) for v in versions}
    authorized = [v for v in versions if grants[v.version_id] is not None]
    if not authorized:
        # An issuer without authority can at most be a public source, whatever it claims.
        return b.done(INSUFFICIENT, [Finding(Reason.ISSUER_NOT_AUTHORIZED, version_id=v.version_id) for v in versions],
                      EvidenceLevel.PUBLIC_SOURCE, considered=versions)

    sel = selector.select(authorized, t, ctx.as_of)
    if not sel.applicable:
        reason = Reason.VALIDITY_UNKNOWN if sel.validity_unknown else Reason.NO_POLICY_AT_DATE
        level = _weakest(g.evidence_level for g in grants.values() if g is not None)
        return b.done(INSUFFICIENT, [Finding(reason)], level, considered=authorized)

    applied = sel.applicable
    evidence = _weakest(grants[v.version_id].evidence_level for v in applied)  # type: ignore[union-attr]
    if len({_payee_key(v) for v in applied}) > 1:
        # Sources that disagree are a source conflict, not an instruction conflict. Never pick the newest.
        return b.done(PolicyDecision.REQUIRES_REVIEW,
                      [Finding(Reason.SOURCE_CONFLICT, "account_number", expected=v.payee.account_number,
                               version_id=v.version_id) for v in applied], evidence, applied=applied)

    policy = applied[0]
    claimed_account = normalize.account(claim.account_number.value) if claim.account_number else ""
    if not claimed_account:
        return b.done(INSUFFICIENT, [Finding(Reason.CLAIM_INCOMPLETE, "account_number")], evidence, applied=applied)

    findings = _compare(claim, policy, claimed_account)
    if findings:
        if any(f.reason is Reason.ACCOUNT_MISMATCH for f in findings):
            for old in sel.ended_before:
                if normalize.account(old.payee.account_number) == claimed_account:
                    findings.append(Finding(Reason.MATCHES_SUPERSEDED_POLICY, "account_number",
                                            expected=policy.payee.account_number, found=old.payee.account_number,
                                            version_id=old.version_id))
        if ctx.injection_detected:
            findings.append(Finding(Reason.PROMPT_INJECTION_DETECTED))
        decision = PolicyDecision.CONFLICT
    else:
        findings = [Finding(Reason.ALL_FIELDS_MATCH, version_id=policy.version_id)]
        decision = PolicyDecision.CONSISTENT
        still_current = policy.valid_to is None or policy.valid_to > ctx.as_of
        if still_current and policy.freshness_deadline is not None and policy.freshness_deadline < ctx.as_of:
            findings.append(Finding(Reason.SOURCE_STALE, version_id=policy.version_id))
            decision = PolicyDecision.REQUIRES_REVIEW
        if ctx.injection_detected:
            findings.append(Finding(Reason.PROMPT_INJECTION_DETECTED))
            decision = PolicyDecision.REQUIRES_REVIEW
        if kind is AssessmentKind.HISTORICAL and decision is PolicyDecision.CONSISTENT:
            b.limitations.append(Limitation.HISTORICAL_ONLY)
    if policy.valid_to is None:
        b.limitations.append(Limitation.END_DATE_UNKNOWN)
    return b.done(decision, findings, evidence, applied=applied, considered=sel.ended_before)


def _compare(claim: Claim, policy: PolicyVersion, claimed_account: str) -> list[Finding]:
    p = policy.payee
    out: list[Finding] = []
    if claimed_account != normalize.account(p.account_number):
        out.append(Finding(Reason.ACCOUNT_MISMATCH, "account_number", p.account_number,
                           claim.account_number.value if claim.account_number else None, policy.version_id))
    if claim.payee_name and normalize.name(claim.payee_name.value) != normalize.name(p.payee_name):
        out.append(Finding(Reason.PAYEE_MISMATCH, "payee_name", p.payee_name, claim.payee_name.value, policy.version_id))
    if claim.currency and normalize.code(claim.currency.value) != normalize.code(p.currency):
        out.append(Finding(Reason.CURRENCY_MISMATCH, "currency", p.currency, claim.currency.value, policy.version_id))
    if claim.swift_bic and p.swift_bic and normalize.code(claim.swift_bic.value) != normalize.code(p.swift_bic):
        out.append(Finding(Reason.SWIFT_MISMATCH, "swift_bic", p.swift_bic, claim.swift_bic.value, policy.version_id))
    if claim.channel and claim.channel.value not in p.channels:
        out.append(Finding(Reason.CHANNEL_NOT_ALLOWED, "channel", ", ".join(p.channels), claim.channel.value,
                           policy.version_id))
    return out


def assess_case(claim: Claim, ctx: EvaluationContext, paid_at: datetime | None, due_at: datetime | None,
                selector: TemporalSelector = DEFAULT_SELECTOR) -> list[Assessment]:
    """Historical and next-payment assessments are separate results, never merged."""
    out = []
    if paid_at is not None:
        out.append(evaluate(claim, ctx, AssessmentKind.HISTORICAL, paid_at, selector))
    if due_at is not None or paid_at is None:
        out.append(evaluate(claim, ctx, AssessmentKind.NEXT_PAYMENT, due_at, selector))
    return out
