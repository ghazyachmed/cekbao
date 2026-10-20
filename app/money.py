"""Deterministic money and FX-quote calculations. All values use Decimal.

Definitions (one quote, source currency S, target currency T):

    fx_rate                   = units of S charged per 1 unit of T
    principal_source          = expected_recipient_amount * fx_rate
    percent_fee_source        = principal_source * percent_fee / 100
    total_source_cost         = principal_source + flat_fee + percent_fee_source
    all_in_rate               = total_source_cost / expected_recipient_amount
    invoice_shortfall_target  = max(0, invoice_amount - expected_recipient_amount
                                       - known_intermediary_fee)
    markup_vs_reference_pct   = (all_in_rate / reference_rate - 1) * 100

Rounding: intermediate values keep full Decimal precision. Output values are
rounded once with ROUND_HALF_UP (2 decimals for money, 6 for rates).
"""
from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_CURRENCIES = {"USD", "IDR", "CNY", "SGD", "EUR", "GBP", "AUD", "HKD"}
_AMOUNT_RE = re.compile(r"^\d{1,13}(\.\d{1,8})?$")
_LABEL_RE = re.compile(r"^[A-Za-z0-9 .,()&'_-]{1,60}$")
MAX_REFERENCE_DEVIATION_PCT = Decimal("25")
STALE_QUOTE_DAYS = 7
CENT = Decimal("0.01")
RATE_Q = Decimal("0.000001")


class QuoteError(ValueError):
    """A quote input is invalid or impossible. The API returns HTTP 422."""


def parse_amount(raw: str, field_name: str, allow_zero: bool = True) -> Decimal:
    """Parse a non-negative decimal string. Floats, signs and exponents fail."""
    if not isinstance(raw, str) or not _AMOUNT_RE.match(raw.strip()):
        raise QuoteError(f"{field_name}: expected a non-negative decimal string such as '1234.50'")
    try:
        value = Decimal(raw.strip())
    except InvalidOperation as exc:  # pragma: no cover - regex blocks this
        raise QuoteError(f"{field_name}: not a decimal value") from exc
    if not allow_zero and value == 0:
        raise QuoteError(f"{field_name}: must be greater than zero")
    return value


def money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def rate(value: Decimal) -> str:
    return str(value.quantize(RATE_Q, rounding=ROUND_HALF_UP))


class QuoteInput(BaseModel):
    """One user-provided, illustrative provider quote. Not a market quote."""

    model_config = ConfigDict(extra="forbid")

    provider_label: str
    source_currency: str
    target_currency: str
    fx_rate: str
    flat_fee: str
    percent_fee: str
    expected_recipient_amount: str
    quote_date: date
    intermediary_fee_known: bool = False
    intermediary_fee_target: str | None = None

    @field_validator("provider_label")
    @classmethod
    def _label(cls, v: str) -> str:
        if not _LABEL_RE.match(v):
            raise ValueError("provider_label: 1-60 letters, digits, spaces or .,()&'_-")
        return v

    @field_validator("source_currency", "target_currency")
    @classmethod
    def _ccy(cls, v: str) -> str:
        v = v.upper()
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"unsupported currency {v!r}")
        return v


class ReferenceRate(BaseModel):
    """Optional student-provided reference rate with its date and source label."""

    model_config = ConfigDict(extra="forbid")

    fx_rate: str
    as_of: date
    source_label: str = Field(min_length=1, max_length=120)


class QuoteResult(BaseModel):
    provider_label: str
    quote_date: str
    stale: bool
    source_currency: str
    target_currency: str
    fx_rate: str
    expected_recipient_amount: str
    principal_source: str
    flat_fee_source: str
    percent_fee_pct: str
    percent_fee_source: str
    total_source_cost: str
    all_in_rate: str
    invoice_shortfall_target: str
    covers_invoice: bool
    intermediary_fees: str
    markup_vs_reference_pct: str | None
    label: str = "USER-PROVIDED ILLUSTRATIVE QUOTE (not a live market quote)"


class QuoteComparison(BaseModel):
    invoice_amount: str | None
    invoice_currency: str | None
    reference_rate: dict | None
    results: list[QuoteResult]
    lowest_cost_covering_invoice: str | None
    cost_difference_source: str | None
    warnings: list[str]
    method_note: str


def _evaluate(q: QuoteInput, invoice: Decimal | None, invoice_ccy: str | None,
              ref: Decimal | None, today: date, warnings: list[str]) -> tuple[QuoteResult, Decimal]:
    if q.source_currency == q.target_currency:
        raise QuoteError(f"{q.provider_label}: source and target currency are the same")
    if invoice_ccy and q.target_currency != invoice_ccy:
        raise QuoteError(
            f"{q.provider_label}: target currency {q.target_currency} does not match invoice currency {invoice_ccy}")
    if q.quote_date > today:
        raise QuoteError(f"{q.provider_label}: quote_date is in the future")

    fx = parse_amount(q.fx_rate, f"{q.provider_label}.fx_rate", allow_zero=False)
    flat = parse_amount(q.flat_fee, f"{q.provider_label}.flat_fee")
    pct = parse_amount(q.percent_fee, f"{q.provider_label}.percent_fee")
    recv = parse_amount(q.expected_recipient_amount, f"{q.provider_label}.expected_recipient_amount", allow_zero=False)
    if pct >= 100:
        raise QuoteError(f"{q.provider_label}: percent_fee must be below 100")
    inter: Decimal | None = None
    if q.intermediary_fee_known:
        if q.intermediary_fee_target is None:
            raise QuoteError(f"{q.provider_label}: intermediary_fee_target is required when intermediary_fee_known is true")
        inter = parse_amount(q.intermediary_fee_target, f"{q.provider_label}.intermediary_fee_target")

    if ref is not None:
        deviation = abs(fx / ref - 1) * 100
        if deviation > MAX_REFERENCE_DEVIATION_PCT:
            raise QuoteError(
                f"{q.provider_label}: fx_rate deviates {deviation.quantize(CENT)}% from the reference rate "
                f"(limit {MAX_REFERENCE_DEVIATION_PCT}%). The quote is implausible. Ask the provider to confirm it.")

    principal = recv * fx
    pct_fee = principal * pct / 100
    total = principal + flat + pct_fee
    all_in = total / recv
    delivered = recv - (inter or Decimal(0))
    shortfall = max(Decimal(0), (invoice - delivered)) if invoice is not None else Decimal(0)
    stale = (today - q.quote_date).days > STALE_QUOTE_DAYS
    if stale:
        warnings.append(f"{q.provider_label}: quote is older than {STALE_QUOTE_DAYS} days. Request a new quote.")
    if pct > 10:
        warnings.append(f"{q.provider_label}: percent fee above 10%. Confirm the fee with the provider.")
    if not q.intermediary_fee_known:
        warnings.append(
            f"{q.provider_label}: intermediary or receiving-bank fees are UNKNOWN. The institution may receive less.")
    markup = None
    if ref is not None:
        markup = str((((all_in / ref) - 1) * 100).quantize(CENT, rounding=ROUND_HALF_UP))

    result = QuoteResult(
        provider_label=q.provider_label,
        quote_date=q.quote_date.isoformat(),
        stale=stale,
        source_currency=q.source_currency,
        target_currency=q.target_currency,
        fx_rate=rate(fx),
        expected_recipient_amount=money(recv),
        principal_source=money(principal),
        flat_fee_source=money(flat),
        percent_fee_pct=str(pct),
        percent_fee_source=money(pct_fee),
        total_source_cost=money(total),
        all_in_rate=rate(all_in),
        invoice_shortfall_target=money(shortfall),
        covers_invoice=shortfall == 0,
        intermediary_fees=("KNOWN: " + money(inter)) if inter is not None else "UNKNOWN",
        markup_vs_reference_pct=markup,
    )
    return result, total


def compare_quotes(quotes: list[QuoteInput], invoice_amount: Decimal | None, invoice_currency: str | None,
                   today: date, reference: ReferenceRate | None = None) -> QuoteComparison:
    if not 2 <= len(quotes) <= 3:
        raise QuoteError("provide two or three quotes")
    labels = [q.provider_label for q in quotes]
    if len(set(labels)) != len(labels):
        raise QuoteError("provider_label values must be unique")
    sources = {q.source_currency for q in quotes}
    if len(sources) != 1:
        raise QuoteError("all quotes must use the same source currency")
    ref_value = None
    if reference is not None:
        if reference.as_of > today:
            raise QuoteError("reference rate date is in the future")
        ref_value = parse_amount(reference.fx_rate, "reference.fx_rate", allow_zero=False)

    warnings: list[str] = []
    evaluated = [_evaluate(q, invoice_amount, invoice_currency, ref_value, today, warnings) for q in quotes]
    covering = [(r, t) for r, t in evaluated if r.covers_invoice]
    best = min(covering, key=lambda rt: rt[1]) if covering else None
    diff = None
    if best is not None and len(covering) > 1:
        others = sorted(t for r, t in covering if r.provider_label != best[0].provider_label)
        diff = money(others[0] - best[1])
    if not covering:
        warnings.append("No quote delivers the full invoice amount. Do not proceed until the shortfall is resolved.")

    return QuoteComparison(
        invoice_amount=money(invoice_amount) if invoice_amount is not None else None,
        invoice_currency=invoice_currency,
        reference_rate=({"fx_rate": reference.fx_rate, "as_of": reference.as_of.isoformat(),
                         "source_label": reference.source_label, "provided_by": "student"}
                        if reference else None),
        results=[r for r, _ in evaluated],
        lowest_cost_covering_invoice=best[0].provider_label if best else None,
        cost_difference_source=diff,
        warnings=warnings,
        method_note=("Deterministic Decimal calculation of user-provided illustrative quotes. CEKBAO did not "
                     "fetch live rates. Figures are estimates for comparison, not offers."),
    )
