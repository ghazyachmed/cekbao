"""Run the end-to-end sandbox scenarios and save execution evidence.

Usage:  python scripts/run_scenarios.py [--out evidence]

The script starts the real FastAPI app in-process (Starlette TestClient) on a
fresh temporary SQLite database. It signs in as the synthetic personas, calls
the same HTTP endpoints as the browser UI and writes one evidence bundle (JSON
and HTML) per scenario plus a summary. Exit code 0 means every expectation held.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import FIXTURES_DIR, Settings  # noqa: E402
from app.main import create_app, load_samples  # noqa: E402

CODES = {u["user_id"]: u["demo_access_code"] for u in json.loads((FIXTURES_DIR / "demo_users.json").read_text())["users"]}


class Actor:
    def __init__(self, app, user_id):
        self.c = TestClient(app)
        r = self.c.post("/api/session/login", json={"user_id": user_id, "access_code": CODES[user_id]})
        r.raise_for_status()
        self.csrf = r.json()["csrf_token"]
        self.user_id = user_id

    def post(self, url, body=None, headers=None, **kw):
        return self.c.post(url, json=body, headers={"X-CSRF-Token": self.csrf, **(headers or {})}, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "evidence"))
    args = ap.parse_args()
    out = Path(args.out)
    (out / "scenarios").mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="cekbao-run-"))
    settings = Settings(db_path=tmp / "run.sqlite3")
    app = create_app(settings)
    samples = load_samples(FIXTURES_DIR)
    by_id = {s["id"]: s for s in samples["tuition_requests"] + samples["payment_evidence"]}
    log: list[str] = []
    results: list[dict] = []

    def say(line: str) -> None:
        print(line)
        log.append(line)

    def expect(name: str, cond: bool, detail: str) -> None:
        results.append({"check": name, "passed": bool(cond), "detail": detail})
        say(f"  [{'PASS' if cond else 'FAIL'}] {name}: {detail}")

    def export(actor: Actor, case_id: str, label: str) -> dict:
        j = actor.c.get(f"/api/cases/{case_id}/evidence.json")
        h = actor.c.get(f"/api/cases/{case_id}/evidence.html")
        (out / "scenarios" / f"{label}.evidence.json").write_bytes(j.content)
        (out / "scenarios" / f"{label}.evidence.html").write_text(h.text)
        b = j.json()
        say(f"  evidence: scenarios/{label}.evidence.json sha256={b['bundle_sha256'][:16]}... "
            f"events={len(b['audit_events'])} chain_valid={b['audit_chain_valid']}")
        return b

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    health = TestClient(app).get("/api/health").json()
    say(f"CEKBAO scenario run started {started} | extraction_mode={health['extraction_mode']} "
        f"| registry {health['registry_version']} sha256={health['registry_sha256'][:16]}...")

    # Scenario A
    say("\n== Scenario A: suspicious international tuition request (persona stu_ayu)")
    s = by_id["A_SUSPICIOUS_INTL"]
    ayu = Actor(app, "stu_ayu")
    cid = ayu.post("/api/cases", {"case_type": "tuition_request", "claimed_institution": s["claimed_institution"],
                                  "message": s["message"]}).json()["case_id"]
    v = ayu.post(f"/api/cases/{cid}/analyze").json()
    pol = v["analysis"]["policy"]
    say(f"  case {cid}: draft -> {v['state']} | overall={pol['overall_status']} decision={pol['decision']}")
    for f in pol["findings"]:
        say(f"    {f['check_id']:<32} {f['status']:<15} observed={f['observed']}")
    for r in pol["risk_signals"]:
        say(f"    RISK {r['signal_id']} ({r['severity']}): \"{r['evidence']}\"")
    expect("A.status", (pol["overall_status"], pol["decision"]) == ("CONFLICT", "HOLD_DO_NOT_PAY"),
           f"{pol['overall_status']} / {pol['decision']}")
    r = ayu.post(f"/api/cases/{cid}/plan/propose", {})
    expect("A.plan_refused", r.status_code == 409, f"propose plan -> HTTP {r.status_code} {r.json()['detail']}")
    draft = v["analysis"]["escalation"]["draft_email"]
    expect("A.escalation_to_registry_contact", draft["to"] == "student-accounts@northbridge-university.example"
           and draft["auto_send"] is False, f"draft to {draft['to']} auto_send={draft['auto_send']}")
    export(ayu, cid, "A_suspicious_international_request")

    # Scenario B
    say("\n== Scenario B: bank-agent offer + payment slips, UMTS-inspired (persona stu_budi)")
    s = by_id["B_UMTS_INSPIRED"]
    budi = Actor(app, "stu_budi")
    cid = budi.post("/api/cases", {"case_type": "payment_evidence", "institution_id": s["institution_id"],
                                   "offer_message": s["offer_message"], "slips": s["slips"]}).json()["case_id"]
    pdf = b"%PDF-1.4\n(Bukti transfer: STATUS LUNAS / PAYMENT SUCCESSFUL)\n%%EOF"
    up = budi.c.post(f"/api/cases/{cid}/uploads", headers={"X-CSRF-Token": budi.csrf},
                     files={"file": ("bukti_transfer_LUNAS.pdf", pdf, "application/pdf")}, data={"slip_id": "TRX-SYN-0002"})
    say(f"  upload receipt for TRX-SYN-0002 -> HTTP {up.status_code} content_stored={up.json().get('content_stored')}")
    v = budi.post(f"/api/cases/{cid}/analyze").json()
    st = v["analysis"]["settlement"]
    say(f"  case {cid}: draft -> {v['state']} | slips={st['slips_submitted']} "
        f"confirmed={st['slips_confirmed_by_institution_ledger']} unconfirmed={st['slips_unconfirmed']} "
        f"conflict={st['slips_in_conflict']}")
    for x in st["results"]:
        say(f"    slip {x['slip_id']}: {x['settlement_status']} next={x['next_action']} "
            f"issues={[i['code'] for i in x['issues']]}")
    got = {x["slip_id"]: x["settlement_status"] for x in st["results"]}
    expect("B.slip_statuses", got == s["expected"], json.dumps(got))
    expect("B.receipt_pdf_not_proof", got["TRX-SYN-0002"] == "PAYMENT_UNCONFIRMED",
           "PDF that says LUNAS/PAYMENT SUCCESSFUL stays PAYMENT_UNCONFIRMED")
    sig = {x["signal_id"] for x in v["analysis"]["policy"]["risk_signals"]}
    expect("B.bank_agent_detected", "BANK_AGENT_IMPERSONATION" in sig, ", ".join(sorted(sig)))
    export(budi, cid, "B_umts_inspired_slip_ledger")

    # Scenario C
    say("\n== Scenario C: request through the approved channel (persona stu_citra)")
    s = by_id["C_LEGITIMATE"]
    citra = Actor(app, "stu_citra")
    cid = citra.post("/api/cases", {"case_type": "tuition_request", "claimed_institution": s["claimed_institution"],
                                    "message": s["message"]}).json()["case_id"]
    v = citra.post(f"/api/cases/{cid}/analyze").json()
    pol = v["analysis"]["policy"]
    say(f"  case {cid}: draft -> {v['state']} | overall={pol['overall_status']} decision={pol['decision']}")
    expect("C.status", pol["overall_status"] == "MATCHED_SOURCE" and v["state"] == "needs_review",
           f"{pol['overall_status']} / {v['state']}")
    q = samples["quotes"]
    v = citra.post(f"/api/cases/{cid}/quotes", {"quotes": q["quotes"], "reference_rate": q["reference_rate"]}).json()
    for res in v["quotes"]["results"]:
        say(f"    quote {res['provider_label']}: total {res['source_currency']} {res['total_source_cost']} "
            f"all-in {res['all_in_rate']} markup {res['markup_vs_reference_pct']}% intermediary {res['intermediary_fees']}")
    expect("C.quote_choice", v["quotes"]["lowest_cost_covering_invoice"] == "Provider B (illustrative)"
           and v["quotes"]["cost_difference_source"] == "61125.00",
           f"lowest={v['quotes']['lowest_cost_covering_invoice']} saves IDR {v['quotes']['cost_difference_source']}")
    v = citra.post(f"/api/cases/{cid}/plan/propose", {"selected_quote_label": "Provider B (illustrative)"}).json()
    p1 = v["plans"][-1]
    r = citra.post(f"/api/cases/{cid}/plan/deny", {"plan_revision": 1, "plan_digest": p1["digest"],
                                                   "reason": "Want to re-check"})
    say(f"  deny revision 1 -> HTTP {r.status_code} state={r.json()['state']}")
    v = citra.post(f"/api/cases/{cid}/plan/propose", {"selected_quote_label": "Provider B (illustrative)"}).json()
    p2 = v["plans"][-1]
    body = {"plan_revision": p2["revision"], "plan_digest": p2["digest"]}
    a1 = citra.post(f"/api/cases/{cid}/plan/approve", body, headers={"Idempotency-Key": "run-scn-c-0001"})
    a2 = citra.post(f"/api/cases/{cid}/plan/approve", body, headers={"Idempotency-Key": "run-scn-c-0001"})
    say(f"  approve rev {p2['revision']} -> HTTP {a1.status_code} {a1.json().get('plan_status')} | replay same key -> "
        f"HTTP {a2.status_code} replay={a2.json().get('idempotent_replay')}")
    expect("C.approved_once", a1.status_code == 200 and a2.json()["plan_id"] == a1.json()["plan_id"],
           a1.json()["execution"])
    b = export(citra, cid, "C_legitimate_approved_plan")
    expect("C.audit_sequence", [e["event_type"] for e in b["audit_events"]] == [
        "CASE_CREATED", "EXTRACTION_COMPLETED", "ANALYSIS_COMPLETED", "ESCALATION_DRAFTED", "QUOTES_COMPARED",
        "PLAN_PROPOSED", "PLAN_DENIED", "PLAN_EDITED", "PLAN_APPROVED"], " > ".join(e["event_type"] for e in b["audit_events"]))

    # Scenario D
    say("\n== Scenario D: incomplete and adversarial inputs (persona stu_ayu)")
    for sid in ("D1_UNKNOWN_INSTITUTION", "D2_PROMPT_INJECTION", "D3_MANIPULATED_LINK", "D4_MISSING_PAYEE"):
        s = by_id[sid]
        cid = ayu.post("/api/cases", {"case_type": "tuition_request", "claimed_institution": s["claimed_institution"],
                                      "message": s["message"]}).json()["case_id"]
        v = ayu.post(f"/api/cases/{cid}/analyze").json()
        pol = v["analysis"]["policy"]
        say(f"  {sid}: {pol['overall_status']} / {pol['decision']} / state {v['state']} | reasons: "
            f"{'; '.join(pol['reasons'][:4])}")
        expect(f"D.{sid}", (pol["overall_status"], pol["decision"]) == (s["expected"]["overall_status"],
                                                                         s["expected"]["decision"]), "fail closed")
        if sid == "D2_PROMPT_INJECTION":
            export(ayu, cid, "D2_prompt_injection")
    # Impossible FX quote on Citra's approved case.
    cid_c = b["case"]["case_id"]
    bad = [dict(samples["quotes"]["quotes"][0], fx_rate="1.00"), samples["quotes"]["quotes"][1]]
    r = citra.post(f"/api/cases/{cid_c}/quotes", {"quotes": bad, "reference_rate": samples["quotes"]["reference_rate"]})
    expect("D.impossible_fx_quote", r.status_code == 422, f"HTTP {r.status_code}: {r.json()['detail'][:90]}")
    # Unauthorized approvals.
    officer = Actor(app, "officer_nbu")
    r = officer.post(f"/api/cases/{cid_c}/plan/approve", body, headers={"Idempotency-Key": "officer-attempt-1"})
    expect("D.reviewer_cannot_approve", r.status_code == 403, f"HTTP {r.status_code}")
    r = ayu.post(f"/api/cases/{cid_c}/plan/approve", body, headers={"Idempotency-Key": "cross-user-attempt-1"})
    expect("D.other_student_cannot_approve", r.status_code == 404, f"HTTP {r.status_code}")
    r = TestClient(app).post(f"/api/cases/{cid_c}/plan/approve", json=body, headers={"Idempotency-Key": "anon-1234"})
    expect("D.anonymous_cannot_approve", r.status_code == 401, f"HTTP {r.status_code}")

    passed = sum(r["passed"] for r in results)
    say(f"\nSUMMARY: {passed}/{len(results)} expectations passed. Mode: {health['extraction_mode']} "
        f"(no live LLM call). Database: temporary file, discarded.")
    (out / "scenario_run.log").write_text("\n".join(log) + "\n")
    (out / "scenario_summary.json").write_text(json.dumps(
        {"started_utc": started, "extraction_mode": health["extraction_mode"], "registry_sha256": health["registry_sha256"],
         "passed": passed, "total": len(results), "results": results}, indent=2) + "\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
