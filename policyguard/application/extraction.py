"""Claim extraction: the model proposes fields, code validates and grounds them.

* ``RulesExtractor`` reads labeled English instructions with regular expressions. No network.
* A paid model (``PaidClaimModel``, e.g. the Nebius adapter) proposes fields with verbatim quotes.
* ``ground`` keeps a model field only if its quote occurs in the instruction and contains the value.
  Ungrounded fields are dropped, never "fixed".
* ``ClaimExtraction`` composes them with the budget ledger. Paid inference runs only after a budget
  reservation succeeds.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Protocol

from policyguard.domain import normalize
from policyguard.domain.model import Claim, ClaimField, Limitation

from .errors import BudgetExhausted, ModelOutputError, ModelUnavailable, TransientModelError

RULES_VERSION = "rules-extractor-2026.10.1"

_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_CURRENCIES = "GBP|USD|EUR|CAD|SGD|AUD|NZD|CHF|JPY|HKD"
_PATTERNS: dict[str, re.Pattern[str]] = {
    "payee_name": re.compile(r"(?im)^\s*(?:payee|beneficiary|account name|pay to)\s*[:\-]\s*(?P<v>[^\n]+?)\s*$"),
    "account_number": re.compile(
        r"(?im)^\s*(?:iban|account(?: number| no\.?)?)\s*[:\-]\s*(?P<v>[A-Z0-9][A-Z0-9 \-]{4,40}[A-Z0-9])\s*$"),
    "swift_bic": re.compile(r"(?im)^\s*(?:swift(?:/bic)?|bic)(?: code)?\s*[:\-]\s*(?P<v>[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b"),
    "bank_name": re.compile(r"(?im)^\s*bank(?: name)?\s*[:\-]\s*(?P<v>[^\n]+?)\s*$"),
    "amount": re.compile(rf"(?P<cur>{_CURRENCIES})\s?(?P<v>\d{{1,3}}(?:,\d{{3}})*(?:\.\d{{2}})?)"),
    "due_date": re.compile(rf"(?i)\b(?:by|due(?: date)?:?|before|on or before)\s+(?P<v>\d{{1,2}} (?:{_MONTHS}) \d{{4}})"),
    "institution_name": re.compile(r"(?P<v>(?:[A-Z][a-z]+ ){1,4}(?:University|Institute of Technology|Institute|College))"),
}
_CHANNELS = [("crypto_wallet", re.compile(r"(?i)\b(crypto|bitcoin|usdt|stablecoin|wallet address)\b")),
             ("gift_card", re.compile(r"(?i)\bgift ?cards?\b")),
             ("card_portal", re.compile(r"(?i)\b(card payment|pay by card|payment portal)\b")),
             ("bank_transfer", re.compile(r"(?i)\b(bank transfer|wire transfer|iban|swift)\b"))]


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class ExtractionResult:
    claim: Claim
    limitations: tuple[Limitation, ...] = ()
    usage: Usage | None = None


class ClaimExtractor(Protocol):
    def extract(self, text: str, hints: dict) -> ExtractionResult: ...


class PaidClaimModel(ClaimExtractor, Protocol):
    model_id: str
    mode: str   # "live" for a real provider; tests use "mock"


class RulesExtractor:
    def extract(self, text: str, hints: dict) -> ExtractionResult:
        found: dict[str, ClaimField] = {}
        for name, rx in _PATTERNS.items():
            m = rx.search(text)
            if m:
                found[name] = ClaimField(m.group("v").strip(), m.group(0).strip(), "rules")
                if name == "amount":
                    found["currency"] = ClaimField(m.group("cur"), m.group(0).strip(), "rules")
        for channel, rx in _CHANNELS:
            m = rx.search(text)
            if m:
                found["channel"] = ClaimField(channel, m.group(0), "rules")
                break
        return ExtractionResult(Claim(**found))


def _squash(s: str) -> str:
    return " ".join(s.split())


def ground(claim: Claim, text: str) -> tuple[Claim, list[str]]:
    """Drop fields whose quote is not in the text or does not contain the value."""
    haystack = _squash(text).casefold()
    kept: dict[str, ClaimField] = {}
    dropped: list[str] = []
    for name in Claim.FIELDS:
        f: ClaimField | None = getattr(claim, name)
        if f is None:
            continue
        quote = _squash(f.quote)
        ok = bool(quote) and quote.casefold() in haystack and _value_in_quote(name, f.value, quote)
        if ok:
            kept[name] = f
        else:
            dropped.append(name)
    return Claim(**kept), dropped


def _value_in_quote(name: str, value: str, quote: str) -> bool:
    if name == "account_number":
        return bool(normalize.account(value)) and normalize.account(value) in normalize.account(quote)
    if name == "channel":
        return True   # the channel is a category inferred from the quote, not a substring of it
    if name == "amount":
        return value.replace(",", "") in quote.replace(",", "")
    return normalize.name(value) in normalize.name(quote)


@dataclass(frozen=True)
class InferenceRecord:
    provider: str
    model_id: str
    mode: str            # live | replay | mock | rules
    latency_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    est_cost_usd: Decimal | None
    outcome: str
    error_code: str | None = None


@dataclass(frozen=True)
class ExtractionOutcome:
    claim: Claim
    limitations: tuple[Limitation, ...]
    record: InferenceRecord

    @property
    def model_version(self) -> str:
        if self.record.mode == "rules":
            return f"rules:{RULES_VERSION}"
        return f"{self.record.provider}:{self.record.model_id}:{self.record.mode}"


class Budget(Protocol):
    def reserve(self, usd: Decimal) -> str: ...
    def settle(self, reservation: str, usd: Decimal, actual_usd: Decimal) -> None: ...
    def release(self, reservation: str, usd: Decimal) -> None: ...


@dataclass
class ClaimExtraction:
    rules: ClaimExtractor
    paid_model: PaidClaimModel | None = None
    budget: Budget | None = None
    provider: str = "nebius"
    estimate_usd: Callable[[str], Decimal] = lambda text: Decimal("0.001")
    cost_usd: Callable[[Usage], Decimal] = lambda usage: Decimal("0")
    monotonic: Callable[[], float] = field(default=time.monotonic)

    def _rules(self, text: str, hints: dict, limitation: Limitation, outcome: str, error: str | None = None
               ) -> ExtractionOutcome:
        res = self.rules.extract(text, hints)
        rec = InferenceRecord(self.provider if error else "none", f"rules:{RULES_VERSION}", "rules", None, None, None,
                              None, outcome, error)
        return ExtractionOutcome(res.claim, (*res.limitations, limitation), rec)

    def run(self, text: str, hints: dict, *, final_attempt: bool) -> ExtractionOutcome:
        if self.paid_model is None or self.budget is None:
            return self._rules(text, hints, Limitation.PAID_INFERENCE_DISABLED, "paid_inference_disabled")
        estimate = self.estimate_usd(text)
        try:
            reservation = self.budget.reserve(estimate)
        except BudgetExhausted:
            return self._rules(text, hints, Limitation.PAID_INFERENCE_DISABLED, "budget_exhausted")
        started = self.monotonic()
        model = self.paid_model
        try:
            res = model.extract(text, hints)
        except TransientModelError as e:
            self.budget.release(reservation, estimate)
            if final_attempt:
                return self._rules(text, hints, Limitation.MODEL_UNAVAILABLE, "provider_unavailable_fallback",
                                   type(e).__name__)
            raise
        except ModelUnavailable as e:
            self.budget.release(reservation, estimate)
            return self._rules(text, hints, Limitation.MODEL_UNAVAILABLE, "provider_error", str(e)[:60])
        except ModelOutputError:
            self.budget.settle(reservation, estimate, estimate)   # the provider charged for the answer
            return self._rules(text, hints, Limitation.MODEL_OUTPUT_REJECTED, "invalid_model_output",
                               "ModelOutputError")
        latency = int((self.monotonic() - started) * 1000)
        actual = self.cost_usd(res.usage) if res.usage else estimate
        self.budget.settle(reservation, estimate, actual)
        claim, dropped = ground(res.claim, text)
        lims = list(res.limitations)
        if dropped:
            lims.append(Limitation.FIELD_NOT_GROUNDED)
        rec = InferenceRecord(self.provider, model.model_id, model.mode, latency,
                              res.usage.prompt_tokens if res.usage else None,
                              res.usage.completion_tokens if res.usage else None, actual,
                              "ok" if not dropped else f"ok_dropped:{','.join(dropped)}")
        return ExtractionOutcome(claim, tuple(lims), rec)


def apply_corrections(claim: Claim, corrections: dict[str, str]) -> Claim:
    """User-entered corrections replace extracted values and are labeled as user input."""
    updates = {k: ClaimField(v.strip(), "Entered by the user", "user") for k, v in corrections.items()
               if k in Claim.FIELDS and v and v.strip()}
    return replace(claim, **updates)
