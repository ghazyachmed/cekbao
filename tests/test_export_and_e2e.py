"""End-to-end scenarios A-D and the evidence export."""
import hashlib
import json
import re

from conftest import CODES, sample_by_id

FORBIDDEN_CLAIMS = re.compile(
    r"(?i)\b(fraud[- ]free|fraud confirmed|bank[- ]verified|recipient verified|100% accurate|official (?:university )?"
    r"partner|payment (?:is )?(?:complete|completed|successful)|has been paid|is paid|settled|loan approved)\b")


def system_text(view: dict) -> str:
    """Text written by CEKBAO itself (not quoted message evidence)."""
    a = view["analysis"] or {}
    pol = a.get("policy") or {}
    parts = [pol.get("overall_status", ""), pol.get("decision", "")]
    parts += [f["explanation"] for f in pol.get("findings", [])]
    parts += [s["explanation"] for s in pol.get("risk_signals", [])]
    if a.get("settlement"):
        parts.append(a["settlement"]["method_note"])
        for r in a["settlement"]["results"]:
            parts += [r["settlement_status"], r["next_action"]] + [i["detail"] for i in r["issues"]]
            parts += [t["event"] for t in r["timeline"] if not t["source"].startswith("UPLOAD")]
    esc = a.get("escalation") or {}
    parts += esc.get("checklist", [])
    return "\n".join(parts)


def test_scenario_a_suspicious_international_request(login, samples):
    ayu = login("stu_ayu")
    s = sample_by_id(samples, "A_SUSPICIOUS_INTL")
    case = ayu.new_tuition_case(s)
    assert case["state"] == "draft"
    v = ayu.analyze(case["case_id"])
    pol = v["analysis"]["policy"]
    assert (pol["overall_status"], pol["decision"]) == ("CONFLICT", "HOLD_DO_NOT_PAY")
    assert v["state"] == "blocked"
    conflicts = {f["check_id"] for f in pol["findings"] if f["status"] == "CONFLICT"}
    assert {"SENDER_DOMAIN", "LINK_DOMAIN", "BENEFICIARY_NAME", "BENEFICIARY_ACCOUNT", "SWIFT_BIC"} <= conflicts
    esc = v["analysis"]["escalation"]
    assert esc["payment_hold"] is True
    draft = esc["draft_email"]
    assert draft["to"] == "student-accounts@northbridge-university.example"  # registry, not the scam sender
    assert draft["auto_send"] is False
    assert "northbridge-university-payments" not in draft["to"]
    events = [e["event_type"] for e in v["audit_events"]]
    assert events == ["CASE_CREATED", "EXTRACTION_COMPLETED", "ANALYSIS_COMPLETED", "PAYMENT_HOLD",
                      "ESCALATION_DRAFTED"]
    assert not FORBIDDEN_CLAIMS.search(system_text(v))


def test_scenario_b_umts_inspired_receipt_ledger_discrepancy(login, samples):
    budi = login("stu_budi")
    s = sample_by_id(samples, "B_UMTS_INSPIRED")
    r = budi.post("/api/cases", json={"case_type": "payment_evidence", "institution_id": s["institution_id"],
                                     "offer_message": s["offer_message"], "slips": s["slips"]})
    v = budi.analyze(r.json()["case_id"])
    got = {x["slip_id"]: x["settlement_status"] for x in v["analysis"]["settlement"]["results"]}
    assert got == s["expected"]
    assert v["state"] == "blocked"
    sigs = {x["signal_id"] for x in v["analysis"]["policy"]["risk_signals"]}
    assert {"BANK_AGENT_IMPERSONATION", "EASY_PAYMENT_OFFER", "DEADLINE_PRESSURE"} <= sigs
    assert v["analysis"]["escalation"]["draft_email"]["to"] == "keuangan@ucn.example"
    assert not FORBIDDEN_CLAIMS.search(system_text(v))
    # Raw offer text is not retained after analysis. Only the redacted version is.
    assert "1239876543" not in json.dumps(v["input"])


def test_scenario_c_full_flow_quotes_plan_approval_export(login, samples):
    citra = login("stu_citra")
    case = citra.new_tuition_case(sample_by_id(samples, "C_LEGITIMATE"))
    v = citra.analyze(case["case_id"])
    assert v["state"] == "needs_review"
    cid = case["case_id"]
    qs = samples["quotes"]
    r = citra.post(f"/api/cases/{cid}/quotes", json={"quotes": qs["quotes"], "reference_rate": qs["reference_rate"]})
    assert r.status_code == 200, r.text
    assert r.json()["quotes"]["lowest_cost_covering_invoice"] == "Provider B (illustrative)"
    r = citra.post(f"/api/cases/{cid}/plan/propose", json={"selected_quote_label": "Provider B (illustrative)"})
    plan = r.json()["plans"][-1]
    assert plan["plan"]["channel"]["note"].startswith("Channel details come from the registry")
    assert plan["plan"]["execution"].startswith("NOT_EXECUTED")
    r = citra.post(f"/api/cases/{cid}/plan/approve", json={"plan_revision": 1, "plan_digest": plan["digest"]},
                   headers={"Idempotency-Key": "scenario-c-0001"})
    assert r.status_code == 200 and r.json()["state"] == "approved"
    v = citra.get(f"/api/cases/{cid}").json()
    assert [e["event_type"] for e in v["audit_events"]] == [
        "CASE_CREATED", "EXTRACTION_COMPLETED", "ANALYSIS_COMPLETED", "ESCALATION_DRAFTED", "QUOTES_COMPARED",
        "PLAN_PROPOSED", "PLAN_APPROVED"]
    assert v["audit_chain_valid"] is True


def test_scenario_d_adversarial_inputs_fail_closed(login, samples):
    ayu = login("stu_ayu")
    for sid in ("D1_UNKNOWN_INSTITUTION", "D2_PROMPT_INJECTION", "D3_MANIPULATED_LINK", "D4_MISSING_PAYEE"):
        s = sample_by_id(samples, sid)
        v = ayu.analyze(ayu.new_tuition_case(s)["case_id"])
        pol = v["analysis"]["policy"]
        assert (pol["overall_status"], pol["decision"]) == (s["expected"]["overall_status"],
                                                             s["expected"]["decision"]), sid
        assert v["state"] == "blocked", sid
    # Impossible FX quote on an allowed case is rejected and logged.
    citra = login("stu_citra")
    cid = citra.analyze(citra.new_tuition_case(sample_by_id(samples, "C_LEGITIMATE"))["case_id"])["case_id"]
    bad = [dict(samples["quotes"]["quotes"][0], fx_rate="1.00"), samples["quotes"]["quotes"][1]]
    r = citra.post(f"/api/cases/{cid}/quotes", json={"quotes": bad, "reference_rate": samples["quotes"]["reference_rate"]})
    assert r.status_code == 422 and "implausible" in r.json()["detail"]
    neg = [dict(samples["quotes"]["quotes"][0], flat_fee="-10"), samples["quotes"]["quotes"][1]]
    assert citra.post(f"/api/cases/{cid}/quotes", json={"quotes": neg}).status_code == 422
    events = [e["event_type"] for e in citra.get(f"/api/cases/{cid}").json()["audit_events"]]
    assert events.count("QUOTES_REJECTED") == 2


def test_analysis_cannot_run_twice(login, samples):
    ayu = login("stu_ayu")
    cid = ayu.analyze(ayu.new_tuition_case(sample_by_id(samples, "A_SUSPICIOUS_INTL"))["case_id"])["case_id"]
    assert ayu.post(f"/api/cases/{cid}/analyze").status_code == 409


def _scenario_c_approved(login, samples):
    citra = login("stu_citra")
    cid = citra.analyze(citra.new_tuition_case(sample_by_id(samples, "C_LEGITIMATE"))["case_id"])["case_id"]
    qs = samples["quotes"]
    citra.post(f"/api/cases/{cid}/quotes", json={"quotes": qs["quotes"], "reference_rate": qs["reference_rate"]})
    plan = citra.post(f"/api/cases/{cid}/plan/propose", json={}).json()["plans"][-1]
    citra.post(f"/api/cases/{cid}/plan/approve", json={"plan_revision": 1, "plan_digest": plan["digest"]},
               headers={"Idempotency-Key": "export-test-0001"})
    return citra, cid


def test_export_is_reproducible_and_matches_audit_log(login, samples, app):
    citra, cid = _scenario_c_approved(login, samples)
    b1 = citra.get(f"/api/cases/{cid}/evidence.json").content
    b2 = citra.get(f"/api/cases/{cid}/evidence.json").content
    assert b1 == b2
    bundle = json.loads(b1)
    stated = bundle.pop("bundle_sha256")
    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == stated
    from app.db import connect
    conn = connect(app.state.svc.settings.db_path)
    db_ids = [r["event_id"] for r in conn.execute("SELECT event_id FROM audit_events WHERE case_id = ? ORDER BY seq",
                                                  (cid,))]
    conn.close()
    assert [e["event_id"] for e in bundle["audit_events"]] == db_ids
    assert bundle["as_of_event_id"] == db_ids[-1]
    assert bundle["audit_chain_valid"] is True


def test_export_contains_no_secrets(login, samples):
    citra, cid = _scenario_c_approved(login, samples)
    text = citra.get(f"/api/cases/{cid}/evidence.json").text + citra.get(f"/api/cases/{cid}/evidence.html").text
    assert citra.csrf not in text
    session_cookie = citra.client.cookies.get("cekbao_session")
    assert session_cookie and session_cookie not in text
    for code in CODES.values():
        assert code not in text
    assert "000123456789" not in text  # full account number never exported
    assert "citra.student@mail.example" not in text
    assert "export-test-0001" not in text  # idempotency key is stored only as a hash


def test_outputs_cite_sources_and_label_synthetic(login, samples):
    citra, cid = _scenario_c_approved(login, samples)
    b = citra.get(f"/api/cases/{cid}/evidence.json").json()
    assert b["institution"]["synthetic"] is True
    assert "SYNTHETIC" in b["synthetic_data_notice"]
    for f in b["findings"]:
        assert f["source_url"] == b["institution"]["source_url"]
        assert f["source_synthetic"] is True
    assert b["institution"]["source_url"] in b["sources_cited"]
    assert b["extraction"]["mode"] == "DETERMINISTIC_DEMO"
    assert any("not bank-level payee authentication" in x for x in b["limitations"])


def test_html_export_escapes_hostile_content(login):
    ayu = login("stu_ayu")
    msg = ("From: x <a@b.example>\nInstitution: <script>alert(1)</script>\nBeneficiary: <img src=x onerror=alert(1)>\n"
           "https://evil.example/\"><script>alert(2)</script>")
    r = ayu.post("/api/cases", json={"case_type": "tuition_request", "message": msg})
    cid = r.json()["case_id"]
    ayu.analyze(cid)
    resp = ayu.get(f"/api/cases/{cid}/evidence.html")
    assert "<script>alert" not in resp.text and "<img src=x" not in resp.text
    assert "&lt;script&gt;" in resp.text
    assert "script-src" not in resp.headers["content-security-policy"]  # no scripts allowed at all
    assert resp.headers["content-disposition"].startswith("attachment")


def test_duplicate_intermediary_requests_flagged(login, samples):
    budi = login("stu_budi")
    s = sample_by_id(samples, "B_UMTS_INSPIRED")
    payload = {"case_type": "payment_evidence", "institution_id": s["institution_id"],
               "offer_message": s["offer_message"], "slips": [s["slips"][1]]}
    first = budi.analyze(budi.post("/api/cases", json=payload).json()["case_id"])
    assert "DUPLICATE_INTERMEDIARY_REQUEST" not in {x["signal_id"] for x in first["analysis"]["policy"]["risk_signals"]}
    payload["slips"] = [s["slips"][2]]
    second = budi.analyze(budi.post("/api/cases", json=payload).json()["case_id"])
    sig = {x["signal_id"]: x for x in second["analysis"]["policy"]["risk_signals"]}
    assert sig["DUPLICATE_INTERMEDIARY_REQUEST"]["severity"] == "high"
    # A slip ID submitted in an earlier case is a repeat as well.
    payload["slips"] = [s["slips"][1]]
    third = budi.analyze(budi.post("/api/cases", json=payload).json()["case_id"])
    issues = {i["code"] for r in third["analysis"]["settlement"]["results"] for i in r["issues"]}
    assert "DUPLICATE_SLIP_ID" in issues


def test_office_sees_same_intermediary_across_students_without_identities(login, samples):
    ayu = login("stu_ayu")
    s = sample_by_id(samples, "A_SUSPICIOUS_INTL")
    ayu.analyze(ayu.new_tuition_case(s)["case_id"])
    second = ayu.analyze(ayu.new_tuition_case(s)["case_id"])
    assert "DUPLICATE_INTERMEDIARY_REQUEST" in {x["signal_id"] for x in second["analysis"]["policy"]["risk_signals"]}
    citra = login("stu_citra")
    citra.analyze(citra.new_tuition_case(s)["case_id"])
    office = login("officer_nbu").get("/api/office/escalations").json()
    counts = {e["cases_with_same_intermediary"] for e in office["escalations"]}
    assert counts == {3}
    text = json.dumps(office)
    assert "stu_ayu" not in text and "stu_citra" not in text and "+1-555-0199" not in text
