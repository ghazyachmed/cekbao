"""Payment-evidence reconciliation (Scenario B).

A slip, a receipt image or a bank screenshot is a claim made by a document.
It never proves that funds reached the institution. Only an institution-side
ledger record (here: a synthetic sandbox fixture) can move a slip to
CONFIRMED_BY_INSTITUTION_LEDGER. Without it the result is PAYMENT_UNCONFIRMED
with next action REQUIRES_INSTITUTION_CHECK.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import NextAction, SettlementStatus
from .money import money, parse_amount
from .registry import InstitutionEntry
from .sanitize import mask_account

DATE_TOLERANCE_DAYS = 2
LEDGER_POSTING_WINDOW_DAYS = 5


class SlipInput(BaseModel):
    """Student-provided slip fields. Unauthenticated claims."""

    model_config = ConfigDict(extra="forbid")

    slip_id: str = Field(pattern=r"^[A-Za-z0-9-]{3,40}$")
    amount: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    transfer_date: date
    destination_account: str = Field(pattern=r"^[0-9 -]{6,30}$")
    destination_name: str = Field(min_length=1, max_length=120)
    payer_reference: str = Field(pattern=r"^[A-Za-z0-9-]{3,40}$")

    @field_validator("amount")
    @classmethod
    def _amount(cls, v: str) -> str:
        parse_amount(v, "amount", allow_zero=False)
        return v


class LedgerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ledger_id: str
    payer_reference: str
    amount: str
    currency: str
    credited_on: date
    channel_id: str
    bank_reference: str | None = None


class BankRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bank_reference: str
    payer_reference: str
    amount: str
    currency: str
    booked_on: date
    destination_account: str
    destination_name: str


class LedgerTool:
    """Read-only lookup in the synthetic institution ledger, scoped by payer."""

    def __init__(self, path: Path):
        data = json.loads(path.read_text())
        self.institution_id: str = data["institution_id"]
        self.notice: str = data["notice"]
        self._records = [LedgerRecord.model_validate(r) for r in data["records"]]

    def records_for(self, institution_id: str, payer_reference: str) -> list[LedgerRecord]:
        if institution_id != self.institution_id:
            return []
        return [r.model_copy() for r in self._records if r.payer_reference == payer_reference]


class BankFeedTool:
    """Read-only lookup in the synthetic sandbox bank feed, scoped by payer."""

    def __init__(self, path: Path):
        data = json.loads(path.read_text())
        self.notice: str = data["notice"]
        self._records = [BankRecord.model_validate(r) for r in data["records"]]

    def lookup(self, payer_reference: str, bank_reference: str) -> BankRecord | None:
        for r in self._records:
            if r.payer_reference == payer_reference and r.bank_reference == bank_reference:
                return r.model_copy()
        return None


def _show(d: Decimal) -> str:
    """Display format with thousands separators. Machine fields keep plain strings."""
    return f"{d.quantize(Decimal('0.01')):,}"


def _acct(v: str) -> str:
    return re.sub(r"[\s-]", "", v)


def reconcile(slips: list[SlipInput], entry: InstitutionEntry, student_ref: str, ledger: LedgerTool,
              bank: BankFeedTool, previously_seen: set[str], uploads: dict[str, list[dict]], today: date) -> dict:
    counts = Counter(s.slip_id for s in slips)
    results = []
    for s in slips:
        issues: list[dict] = []
        timeline: list[dict] = []
        amount = parse_amount(s.amount, "amount", allow_zero=False)
        timeline.append({"date": s.transfer_date.isoformat(), "source": "SLIP (student-provided, unauthenticated)",
                         "event": f"Slip claims transfer of {s.currency} {_show(amount)} to "
                                  f"{mask_account(s.destination_account)}"})
        for u in uploads.get(s.slip_id, []):
            timeline.append({"date": u["created_at"][:10], "source": "UPLOAD (metadata only)",
                             "event": f"Receipt file {u['safe_name']} ({u['media_type']}, {u['size']} bytes, "
                                      f"sha256 {u['sha256'][:12]}...). File content is not used as proof."})

        if s.payer_reference != student_ref:
            issues.append({"code": "PAYER_REFERENCE_MISMATCH",
                           "detail": "The slip payer reference is not your reference. CEKBAO does not look up "
                                     "other students' records."})
        if counts[s.slip_id] > 1 or s.slip_id in previously_seen:
            issues.append({"code": "DUPLICATE_SLIP_ID",
                           "detail": "This slip ID appears more than once. One transfer has one bank reference."})
        if s.transfer_date > today:
            issues.append({"code": "FUTURE_DATE", "detail": "The slip date is in the future."})
        official = [c for c in entry.approved_channels if c.account_matches(s.destination_account)]
        if not official:
            issues.append({"code": "WRONG_DESTINATION",
                           "detail": "The destination account is not an approved institution account in the "
                                     "registry."})

        bank_rec = ledger_match = None
        if not any(i["code"] == "PAYER_REFERENCE_MISMATCH" for i in issues):
            bank_rec = bank.lookup(student_ref, s.slip_id)
            if bank_rec is None:
                timeline.append({"date": None, "source": "BANK FEED (synthetic sandbox)",
                                 "event": "No outgoing transfer with this reference."})
            else:
                timeline.append({"date": bank_rec.booked_on.isoformat(), "source": "BANK FEED (synthetic sandbox)",
                                 "event": f"Outgoing {bank_rec.currency} {_show(Decimal(bank_rec.amount))} to "
                                          f"{mask_account(bank_rec.destination_account)}"})
                if Decimal(bank_rec.amount) != amount:
                    issues.append({"code": "AMOUNT_MISMATCH",
                                   "detail": f"Slip amount {_show(amount)} differs from the bank record "
                                             f"{_show(Decimal(bank_rec.amount))}."})
                if _acct(bank_rec.destination_account) != _acct(s.destination_account):
                    issues.append({"code": "DESTINATION_MISMATCH",
                                   "detail": "The bank record shows a different destination account."})
                if abs((bank_rec.booked_on - s.transfer_date).days) > DATE_TOLERANCE_DAYS:
                    issues.append({"code": "DATE_MISMATCH",
                                   "detail": f"Slip date {s.transfer_date} differs from bank booking date "
                                             f"{bank_rec.booked_on} by more than {DATE_TOLERANCE_DAYS} days."})
            for rec in ledger.records_for(entry.institution_id, student_ref):
                same_ref = rec.bank_reference == s.slip_id
                close = abs((rec.credited_on - s.transfer_date).days) <= LEDGER_POSTING_WINDOW_DAYS
                if same_ref and Decimal(rec.amount) != amount:
                    issues.append({"code": "LEDGER_AMOUNT_MISMATCH",
                                   "detail": "The institution ledger holds this reference with a different amount."})
                elif same_ref and close and rec.currency == s.currency:
                    ledger_match = rec
            if ledger_match:
                timeline.append({"date": ledger_match.credited_on.isoformat(),
                                 "source": "INSTITUTION LEDGER (synthetic sandbox)",
                                 "event": f"Credited as {ledger_match.ledger_id} via {ledger_match.channel_id}"})
            else:
                timeline.append({"date": None, "source": "INSTITUTION LEDGER (synthetic sandbox)",
                                 "event": "No matching credit for this slip."})

        if issues:
            status = SettlementStatus.CONFLICT
            action = NextAction.CONTACT_BANK_AND_INSTITUTION
        elif ledger_match:
            status = SettlementStatus.CONFIRMED_BY_INSTITUTION_LEDGER
            action = NextAction.KEEP_INSTITUTION_RECEIPT
        else:
            status = SettlementStatus.PAYMENT_UNCONFIRMED
            action = NextAction.REQUIRES_INSTITUTION_CHECK
        timeline.sort(key=lambda e: (e["date"] is None, e["date"] or ""))
        results.append({
            "slip_id": s.slip_id,
            "claimed_amount": f"{s.currency} {money(amount)}",
            "claimed_destination": mask_account(s.destination_account),
            "settlement_status": status.value,
            "next_action": action.value,
            "issues": issues,
            "timeline": timeline,
            "ledger_record_id": ledger_match.ledger_id if ledger_match else None,
        })

    confirmed = sum(r["settlement_status"] == SettlementStatus.CONFIRMED_BY_INSTITUTION_LEDGER.value for r in results)
    return {
        "slips_submitted": len(results),
        "slips_confirmed_by_institution_ledger": confirmed,
        "slips_unconfirmed": sum(r["settlement_status"] == SettlementStatus.PAYMENT_UNCONFIRMED.value for r in results),
        "slips_in_conflict": sum(r["settlement_status"] == SettlementStatus.CONFLICT.value for r in results),
        "results": results,
        "method_note": ("A slip or receipt is a document claim. Only an institution ledger record confirms "
                        "settlement. Ledger and bank feed are SYNTHETIC sandbox fixtures."),
        "ledger_notice": ledger.notice,
        "bank_feed_notice": bank.notice,
    }
