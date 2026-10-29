"""Domain types. Pure Python: no framework, database or SDK imports.

Three result dimensions stay separate on purpose:

* ``PolicyDecision``: does the instruction agree with the applicable policy?
* ``EvidenceLevel``: how strong is the evidence behind that policy?
* ``TransactionStatus``: did money move? Only an authorized official
  transaction system can set SETTLED. Text, screenshots, OCR, domains and
  hashes never do.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class PolicyDecision(StrEnum):
    CONSISTENT = "CONSISTENT"
    CONFLICT = "CONFLICT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class EvidenceLevel(StrEnum):
    PUBLIC_SOURCE = "PUBLIC_SOURCE"
    INSTITUTION_ATTESTED = "INSTITUTION_ATTESTED"
    OFFICIAL_TRANSACTION = "OFFICIAL_TRANSACTION"


EVIDENCE_RANK = {EvidenceLevel.PUBLIC_SOURCE: 1, EvidenceLevel.INSTITUTION_ATTESTED: 2,
                 EvidenceLevel.OFFICIAL_TRANSACTION: 3}


class TransactionStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class AssessmentKind(StrEnum):
    HISTORICAL = "HISTORICAL"        # a payment that was already made, judged at its payment date
    NEXT_PAYMENT = "NEXT_PAYMENT"    # a payment the user intends to make, judged at the intended date


class ApprovalStatus(StrEnum):
    DISCOVERED = "DISCOVERED"   # found by ingestion; never used for decisions
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Reason(StrEnum):
    # instruction vs policy
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"
    PAYEE_MISMATCH = "PAYEE_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    SWIFT_MISMATCH = "SWIFT_MISMATCH"
    CHANNEL_NOT_ALLOWED = "CHANNEL_NOT_ALLOWED"
    MATCHES_SUPERSEDED_POLICY = "MATCHES_SUPERSEDED_POLICY"
    # source vs source
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    # evidence gaps
    UNKNOWN_INSTITUTION = "UNKNOWN_INSTITUTION"
    NO_POLICY_FOUND = "NO_POLICY_FOUND"
    ISSUER_NOT_AUTHORIZED = "ISSUER_NOT_AUTHORIZED"
    NO_POLICY_AT_DATE = "NO_POLICY_AT_DATE"
    VALIDITY_UNKNOWN = "VALIDITY_UNKNOWN"
    DATE_UNKNOWN = "DATE_UNKNOWN"
    CLAIM_INCOMPLETE = "CLAIM_INCOMPLETE"
    SOURCE_STALE = "SOURCE_STALE"
    # input safety
    PROMPT_INJECTION_DETECTED = "PROMPT_INJECTION_DETECTED"
    ALL_FIELDS_MATCH = "ALL_FIELDS_MATCH"


class Limitation(StrEnum):
    END_DATE_UNKNOWN = "END_DATE_UNKNOWN"
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    NOT_A_SETTLEMENT_CHECK = "NOT_A_SETTLEMENT_CHECK"
    MODEL_OUTPUT_REJECTED = "MODEL_OUTPUT_REJECTED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    PAID_INFERENCE_DISABLED = "PAID_INFERENCE_DISABLED"
    FIELD_NOT_GROUNDED = "FIELD_NOT_GROUNDED"
    SYNTHETIC_DATA = "SYNTHETIC_DATA"


class NextAction(StrEnum):
    PAY_ONLY_THROUGH_OFFICIAL_CHANNEL = "PAY_ONLY_THROUGH_OFFICIAL_CHANNEL"
    DO_NOT_PAY_CONTACT_INSTITUTION = "DO_NOT_PAY_CONTACT_INSTITUTION"
    REQUEST_INSTITUTION_CONFIRMATION = "REQUEST_INSTITUTION_CONFIRMATION"
    WAIT_FOR_INSTITUTION_REVIEW = "WAIT_FOR_INSTITUTION_REVIEW"
    PROVIDE_PAYMENT_DATE = "PROVIDE_PAYMENT_DATE"


@dataclass(frozen=True)
class Institution:
    institution_id: str
    tenant_id: str
    name: str
    timezone: str
    official_contact_url: str | None = None   # approved destination for next-action links
    aliases: tuple[str, ...] = ()
    synthetic: bool = True


@dataclass(frozen=True)
class AuthorityGrant:
    """Who may publish payment policy for an institution, and for how long."""
    grant_id: str
    tenant_id: str
    institution_id: str
    issuer_id: str
    authority_scope: str
    verification_method: str
    evidence_level: EvidenceLevel
    valid_from: datetime | None
    valid_to: datetime | None
    recorded_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    tenant_id: str
    institution_id: str
    url: str
    title: str
    issuer_id: str
    language: str
    content_hash: str
    fetched_at: datetime
    object_key: str | None = None
    synthetic: bool = True


@dataclass(frozen=True)
class PayeeDetails:
    payee_name: str
    account_number: str
    currency: str
    bank_name: str | None = None
    swift_bic: str | None = None
    channels: tuple[str, ...] = ("bank_transfer",)


@dataclass(frozen=True)
class Citation:
    source_id: str
    source_url: str
    source_title: str
    quote: str                  # original language, verbatim
    locator: str                # e.g. "Section 3, paragraph 2"
    language: str
    translation: str | None = None   # shown only with an explicit translation label


@dataclass(frozen=True)
class PolicyVersion:
    tenant_id: str
    institution_id: str
    policy_id: str
    version_id: str
    version_label: str
    source_url: str
    source_hash: str
    issuer_id: str
    authority_scope: str
    verification_method: str
    evidence_level: EvidenceLevel
    valid_from: datetime | None
    valid_to: datetime | None
    valid_tz: str
    recorded_at: datetime
    payee: PayeeDetails
    citation: Citation
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED
    supersedes_version_id: str | None = None
    revoked_at: datetime | None = None
    fetched_at: datetime | None = None
    verified_at: datetime | None = None
    freshness_deadline: datetime | None = None
    document_object_key: str | None = None
    extraction_version: str = "manual-1"
    synthetic: bool = True


@dataclass(frozen=True)
class ClaimField:
    value: str
    quote: str          # verbatim span from the instruction that supports the value
    source: str = "model"   # model | rules | user


@dataclass(frozen=True)
class Claim:
    """What a payment instruction asserts. Values are claims, not facts."""
    institution_name: ClaimField | None = None
    payee_name: ClaimField | None = None
    account_number: ClaimField | None = None
    bank_name: ClaimField | None = None
    swift_bic: ClaimField | None = None
    amount: ClaimField | None = None
    currency: ClaimField | None = None
    channel: ClaimField | None = None
    due_date: ClaimField | None = None

    FIELDS = ("institution_name", "payee_name", "account_number", "bank_name", "swift_bic", "amount",
              "currency", "channel", "due_date")

    def as_dict(self) -> dict[str, dict | None]:
        out: dict[str, dict | None] = {}
        for name in self.FIELDS:
            f = getattr(self, name)
            out[name] = None if f is None else {"value": f.value, "quote": f.quote, "source": f.source}
        return out

    @property
    def amount_decimal(self) -> Decimal | None:
        if self.amount is None:
            return None
        try:
            return Decimal(self.amount.value.replace(",", ""))
        except ArithmeticError:
            return None


@dataclass(frozen=True)
class Finding:
    reason: Reason
    field: str | None = None
    expected: str | None = None
    found: str | None = None
    version_id: str | None = None


@dataclass(frozen=True)
class Assessment:
    kind: AssessmentKind
    target_time: datetime | None
    decision: PolicyDecision
    evidence_level: EvidenceLevel | None
    transaction_status: TransactionStatus
    next_action: NextAction
    findings: tuple[Finding, ...]
    limitations: tuple[Limitation, ...]
    applied_version_ids: tuple[str, ...]
    considered_version_ids: tuple[str, ...]
    rule_version: str


@dataclass(frozen=True)
class EvaluationContext:
    """Everything the rules read. Built from one consistent snapshot."""
    tenant_id: str
    institution: Institution | None
    versions: tuple[PolicyVersion, ...]
    grants: tuple[AuthorityGrant, ...]
    as_of: datetime          # recorded-time axis: what the system knew
    injection_detected: bool = False
    extra_limitations: tuple[Limitation, ...] = field(default_factory=tuple)
