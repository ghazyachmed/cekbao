"""Typed data models shared by the engine, the API and the evidence export."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CheckStatus(str, Enum):
    """Result of one comparison against the curated trusted-channel registry.

    MATCHED_SOURCE means the field matches the registry entry. It does not
    mean CEKBAO authenticated the payee against a bank registry.
    """

    MATCHED_SOURCE = "MATCHED_SOURCE"
    CONFLICT = "CONFLICT"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"


class Decision(str, Enum):
    HOLD_DO_NOT_PAY = "HOLD_DO_NOT_PAY"
    PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION = "PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION"


class CaseState(str, Enum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    BLOCKED = "blocked"


class SettlementStatus(str, Enum):
    """Settlement status for a payment slip.

    Only an institution-side record can move a slip to
    CONFIRMED_BY_INSTITUTION_LEDGER. A slip, a screenshot or a model
    interpretation alone never does.
    """

    CONFIRMED_BY_INSTITUTION_LEDGER = "CONFIRMED_BY_INSTITUTION_LEDGER"
    PAYMENT_UNCONFIRMED = "PAYMENT_UNCONFIRMED"
    CONFLICT = "CONFLICT"


class NextAction(str, Enum):
    REQUIRES_INSTITUTION_CHECK = "REQUIRES_INSTITUTION_CHECK"
    CONTACT_BANK_AND_INSTITUTION = "CONTACT_BANK_AND_INSTITUTION"
    KEEP_INSTITUTION_RECEIPT = "KEEP_INSTITUTION_RECEIPT"


class ExtractionMode(str, Enum):
    DETERMINISTIC_DEMO = "DETERMINISTIC_DEMO"
    LLM_TOOL_CALLING = "LLM_TOOL_CALLING"
    DETERMINISTIC_FALLBACK_AFTER_LLM_ERROR = "DETERMINISTIC_FALLBACK_AFTER_LLM_ERROR"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


class PaymentMethod(str, Enum):
    INSTITUTION_PORTAL = "institution_portal"
    INTERNATIONAL_WIRE = "international_wire"
    VIRTUAL_ACCOUNT = "virtual_account"
    DOMESTIC_TRANSFER = "domestic_transfer"
    CARD = "card"
    CRYPTO = "crypto"
    GIFT_CARD = "gift_card"
    CASH_OR_AGENT = "cash_or_agent"
    E_WALLET = "e_wallet"
    MONEY_TRANSFER_OPERATOR = "money_transfer_operator"
    PERSONAL_ACCOUNT = "personal_account"


class ExtractedRequest(BaseModel):
    """Structured fields taken from a pasted payment request.

    Values are untrusted. The policy engine re-checks every value against the
    registry. Account numbers stay server-side and are masked in exports.
    """

    model_config = ConfigDict(extra="forbid")

    sender_email: str | None = None
    sender_domain: str | None = None
    sender_display_name: str | None = None
    claimed_institution: str | None = None
    amount: str | None = None
    currency: str | None = None
    beneficiary_name: str | None = None
    beneficiary_account: str | None = None
    swift_bic: str | None = None
    bank_name: str | None = None
    bank_country: str | None = None
    payment_methods: list[PaymentMethod] = Field(default_factory=list)
    deadline_text: str | None = None
    urls: list[str] = Field(default_factory=list)
    contact_phones: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    check_id: str
    label: str
    status: CheckStatus
    required: bool
    observed: str | None = None
    expected: str | None = None
    explanation: str
    source_url: str | None = None
    source_synthetic: bool = True


class RiskSignal(BaseModel):
    signal_id: str
    severity: Severity
    evidence: str
    explanation: str
    source_url: str | None = None


class PolicyResult(BaseModel):
    overall_status: CheckStatus
    decision: Decision
    findings: list[Finding]
    risk_signals: list[RiskSignal]
    reasons: list[str]
