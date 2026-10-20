"""FX-quote calculations: Decimal arithmetic, invalid and impossible inputs."""
from datetime import date
from decimal import Decimal

import pytest

from app.money import QuoteError, QuoteInput, ReferenceRate, compare_quotes, parse_amount

TODAY = date(2026, 10, 20)


def q(label="P1", fx="16450.00", flat="50000.00", pct="0.50", recv="500.00", qdate="2026-10-19", inter=None):
    d = dict(provider_label=label, source_currency="IDR", target_currency="USD", fx_rate=fx, flat_fee=flat,
             percent_fee=pct, expected_recipient_amount=recv, quote_date=qdate)
    if inter is not None:
        d.update(intermediary_fee_known=True, intermediary_fee_target=inter)
    return QuoteInput(**d)


def test_all_in_cost_exact_decimal():
    ref = ReferenceRate(fx_rate="16300.00", as_of=date(2026, 10, 19), source_label="illustrative")
    res = compare_quotes([q("A"), q("B", fx="16210.00", flat="150000.00", pct="0.00", inter="0.00")],
                         Decimal("500.00"), "USD", TODAY, ref)
    a, b = res.results
    # A: 500 * 16450 = 8,225,000 ; 0.5% = 41,125 ; + 50,000 flat = 8,316,125.00
    assert a.principal_source == "8225000.00"
    assert a.percent_fee_source == "41125.00"
    assert a.total_source_cost == "8316125.00"
    assert a.all_in_rate == "16632.250000"
    assert a.markup_vs_reference_pct == "2.04"
    assert a.intermediary_fees == "UNKNOWN"
    # B: 500 * 16210 = 8,105,000 + 150,000 = 8,255,000.00
    assert b.total_source_cost == "8255000.00"
    assert b.intermediary_fees == "KNOWN: 0.00"
    assert res.lowest_cost_covering_invoice == "B"
    assert res.cost_difference_source == "61125.00"
    assert any("UNKNOWN" in w for w in res.warnings)
    assert "did not fetch live rates" in res.method_note


def test_float_precision_trap_is_avoided():
    res = compare_quotes([q("A", fx="0.1", flat="0.2", pct="0", recv="3"), q("B", fx="0.1", flat="0", pct="0", recv="3")],
                         None, None, TODAY)
    # 3 * 0.1 + 0.2 = 0.5 exactly in Decimal (binary floats give 0.5000000000000001)
    assert res.results[0].total_source_cost == "0.50"


@pytest.mark.parametrize("bad", ["-1", "1e5", "abc", "", "1,000", " ", "0x10"])
def test_parse_amount_rejects_invalid(bad):
    with pytest.raises(QuoteError):
        parse_amount(bad, "x")


def test_negative_fee_rejected():
    with pytest.raises(QuoteError):
        compare_quotes([q("A", flat="-5"), q("B")], None, None, TODAY)


def test_zero_rate_rejected():
    with pytest.raises(QuoteError, match="greater than zero"):
        compare_quotes([q("A", fx="0"), q("B")], None, None, TODAY)


def test_percent_fee_100_rejected():
    with pytest.raises(QuoteError, match="below 100"):
        compare_quotes([q("A", pct="100"), q("B")], None, None, TODAY)


def test_impossible_rate_vs_reference_rejected():
    ref = ReferenceRate(fx_rate="16300.00", as_of=date(2026, 10, 19), source_label="illustrative")
    with pytest.raises(QuoteError, match="implausible"):
        compare_quotes([q("A", fx="1.00"), q("B")], None, None, TODAY, ref)


def test_future_quote_date_rejected():
    with pytest.raises(QuoteError, match="future"):
        compare_quotes([q("A", qdate="2026-12-01"), q("B")], None, None, TODAY)


def test_currency_mismatch_with_invoice_rejected():
    with pytest.raises(QuoteError, match="does not match invoice currency"):
        compare_quotes([q("A"), q("B")], Decimal("500"), "SGD", TODAY)


def test_shortfall_flags_quote_that_does_not_cover_invoice():
    res = compare_quotes([q("A", recv="480.00"), q("B", recv="500.00", inter="25.00")], Decimal("500.00"), "USD", TODAY)
    assert res.results[0].covers_invoice is False and res.results[0].invoice_shortfall_target == "20.00"
    assert res.results[1].covers_invoice is False and res.results[1].invoice_shortfall_target == "25.00"
    assert res.lowest_cost_covering_invoice is None
    assert any("No quote delivers" in w for w in res.warnings)


def test_stale_quote_warns():
    res = compare_quotes([q("A", qdate="2026-09-01"), q("B")], None, None, TODAY)
    assert res.results[0].stale is True


def test_duplicate_labels_and_count_rejected():
    with pytest.raises(QuoteError):
        compare_quotes([q("A"), q("A")], None, None, TODAY)
    with pytest.raises(QuoteError):
        compare_quotes([q("A")], None, None, TODAY)
