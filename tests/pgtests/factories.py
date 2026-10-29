"""Synthetic builders for PolicyGuard tests. All institutions and accounts are fictional."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from policyguard.domain.model import (
    ApprovalStatus,
    AuthorityGrant,
    Citation,
    Claim,
    ClaimField,
    EvaluationContext,
    EvidenceLevel,
    Institution,
    PayeeDetails,
    PolicyVersion,
)

TENANT = "tenant-a"
INST = "inst-aster"


def utc(y: int, m: int, d: int, h: int = 0) -> datetime:
    return datetime(y, m, d, h, tzinfo=UTC)


def institution(**kw) -> Institution:
    base = Institution(INST, TENANT, "Aster Bay University", "Europe/London",
                       official_contact_url="https://bursar.asterbay.example/contact")
    return replace(base, **kw)


def grant(**kw) -> AuthorityGrant:
    base = AuthorityGrant("grant-1", TENANT, INST, "asterbay-bursar", "tuition_payment_instructions",
                          "registry_contract", EvidenceLevel.INSTITUTION_ATTESTED, utc(2025, 1, 1), None,
                          utc(2025, 1, 1))
    return replace(base, **kw)


def version(version_id: str = "v1", *, account: str = "GB29 SYNT 6016 1331 9268 19", payee: str = "Aster Bay University",
            valid_from: datetime | None = utc(2026, 1, 1), valid_to: datetime | None = None, **kw) -> PolicyVersion:
    base = PolicyVersion(
        tenant_id=TENANT, institution_id=INST, policy_id="pol-tuition", version_id=version_id,
        version_label=version_id, source_url="https://bursar.asterbay.example/pay", source_hash="sha256:aa",
        issuer_id="asterbay-bursar", authority_scope="tuition_payment_instructions",
        verification_method="registry_contract", evidence_level=EvidenceLevel.INSTITUTION_ATTESTED,
        valid_from=valid_from, valid_to=valid_to, valid_tz="Europe/London", recorded_at=utc(2025, 12, 1),
        payee=PayeeDetails(payee, account, "GBP", "Synthetic Bank plc", "SYNTGB2L", ("bank_transfer",)),
        citation=Citation("src-1", "https://bursar.asterbay.example/pay", "How to pay tuition",
                          f"Pay tuition to {payee}, account {account}.", "Section 2", "en"),
        approval_status=ApprovalStatus.APPROVED)
    return replace(base, **kw)


def claim(account: str | None = "GB29SYNT60161331926819", payee: str | None = "Aster Bay University",
          currency: str | None = "GBP", channel: str | None = "bank_transfer", swift: str | None = None) -> Claim:
    def f(v: str | None) -> ClaimField | None:
        return None if v is None else ClaimField(v, v, "rules")
    return Claim(institution_name=f("Aster Bay University"), payee_name=f(payee), account_number=f(account),
                 currency=f(currency), channel=f(channel), swift_bic=f(swift))


def ctx(versions=(), grants=None, inst=..., as_of: datetime = utc(2026, 10, 28), **kw) -> EvaluationContext:
    return EvaluationContext(TENANT, institution() if inst is ... else inst, tuple(versions),
                             tuple([grant()] if grants is None else grants), as_of, **kw)
