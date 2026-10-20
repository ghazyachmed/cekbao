"""Scenario B: slip vs bank feed vs institution ledger (UMTS-inspired, synthetic)."""
from datetime import date

from app.config import FIXTURES_DIR
from app.registry import Registry
from app.settlement import BankFeedTool, LedgerTool, SlipInput, reconcile

REG = Registry(FIXTURES_DIR / "registry.json")
UCN = REG.get("SYN-ID-UCN")
LEDGER = LedgerTool(FIXTURES_DIR / "ledgers" / "ucn_institution_ledger.json")
BANK = BankFeedTool(FIXTURES_DIR / "ledgers" / "sandbox_bank_feed.json")
REF = "UCN-SYN-2025-0042"
VA = "8808000000420042"
TODAY = date(2026, 10, 20)


def slip(sid, amount="7500000.00", d="2025-01-15", dest=VA, ref=REF):
    return SlipInput(slip_id=sid, amount=amount, currency="IDR", transfer_date=d, destination_account=dest,
                     destination_name="Universitas Contoh Nusantara", payer_reference=ref)


def check(slips, seen=None, uploads=None):
    out = reconcile(slips, UCN, REF, LEDGER, BANK, seen or set(), uploads or {}, TODAY)
    return {r["slip_id"] + f"#{i}": r for i, r in enumerate(out["results"])}, out


def codes(r):
    return {i["code"] for i in r["issues"]}


def test_matching_ledger_record_confirms():
    res, out = check([slip("TRX-SYN-0001")])
    r = res["TRX-SYN-0001#0"]
    assert r["settlement_status"] == "CONFIRMED_BY_INSTITUTION_LEDGER"
    assert r["ledger_record_id"] == "UCN-LGR-0001"
    assert out["slips_confirmed_by_institution_ledger"] == 1


def test_slip_without_ledger_record_is_unconfirmed_not_paid():
    res, _ = check([slip("TRX-SYN-0002", d="2025-02-03")])
    r = res["TRX-SYN-0002#0"]
    assert r["settlement_status"] == "PAYMENT_UNCONFIRMED"
    assert r["next_action"] == "REQUIRES_INSTITUTION_CHECK"
    sources = [t["source"] for t in r["timeline"]]
    assert any("INSTITUTION LEDGER" in s for s in sources) and any("BANK FEED" in s for s in sources)


def test_repeated_slip_id_conflicts():
    res, _ = check([slip("TRX-SYN-0002", d="2025-02-03"), slip("TRX-SYN-0002", d="2025-02-03")])
    assert all("DUPLICATE_SLIP_ID" in codes(r) for r in res.values())


def test_slip_id_seen_in_earlier_case_conflicts():
    res, _ = check([slip("TRX-SYN-0001")], seen={"TRX-SYN-0001"})
    assert res["TRX-SYN-0001#0"]["settlement_status"] == "CONFLICT"


def test_altered_amount_conflicts():
    res, _ = check([slip("TRX-SYN-0003", d="2025-02-04")])  # bank shows 750,000
    r = res["TRX-SYN-0003#0"]
    assert r["settlement_status"] == "CONFLICT" and "AMOUNT_MISMATCH" in codes(r)


def test_wrong_destination_conflicts():
    res, _ = check([slip("TRX-SYN-0004", d="2025-02-05", dest="1239876543")])
    r = res["TRX-SYN-0004#0"]
    assert r["settlement_status"] == "CONFLICT" and "WRONG_DESTINATION" in codes(r)


def test_inconsistent_dates_conflict():
    res, _ = check([slip("TRX-SYN-0005", d="2025-02-10")])  # bank booked 2025-01-20
    assert "DATE_MISMATCH" in codes(res["TRX-SYN-0005#0"])


def test_future_date_conflicts():
    res, _ = check([slip("TRX-SYN-0099", d="2027-01-01")])
    assert "FUTURE_DATE" in codes(res["TRX-SYN-0099#0"])


def test_ledger_amount_mismatch_on_same_reference():
    res, _ = check([slip("TRX-SYN-0001", amount="8500000.00")])
    assert "LEDGER_AMOUNT_MISMATCH" in codes(res["TRX-SYN-0001#0"])


def test_other_students_ledger_is_never_queried():
    # TRX-SYN-9001 belongs to UCN-SYN-2025-0077. The student cannot use it.
    res, _ = check([slip("TRX-SYN-9001", d="2025-01-16", dest="8808000000770077", ref="UCN-SYN-2025-0077")])
    r = res["TRX-SYN-9001#0"]
    assert "PAYER_REFERENCE_MISMATCH" in codes(r)
    assert r["ledger_record_id"] is None
    assert not any("Credited" in t["event"] for t in r["timeline"])


def test_ledger_tool_is_scoped_by_payer():
    recs = LEDGER.records_for("SYN-ID-UCN", REF)
    assert recs and all(r.payer_reference == REF for r in recs)
    assert LEDGER.records_for("SYN-US-NBU", REF) == []


def test_upload_metadata_never_changes_status():
    uploads = {"TRX-SYN-0002": [{"created_at": "2026-10-20T04:00:00", "safe_name": "slip_LUNAS.pdf",
                                 "media_type": "application/pdf", "size": 1200, "sha256": "ab" * 32}]}
    res, _ = check([slip("TRX-SYN-0002", d="2025-02-03")], uploads=uploads)
    r = res["TRX-SYN-0002#0"]
    assert r["settlement_status"] == "PAYMENT_UNCONFIRMED"
    assert any("not used as proof" in t["event"] for t in r["timeline"])
