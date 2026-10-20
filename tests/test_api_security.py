"""Sessions, CSRF, roles, object-level access, idempotency and uploads (integration)."""
from fastapi.testclient import TestClient

from conftest import CODES, sample_by_id


def legit_case(login, samples):
    citra = login("stu_citra")
    case = citra.new_tuition_case(sample_by_id(samples, "C_LEGITIMATE"))
    v = citra.analyze(case["case_id"])
    assert v["state"] == "needs_review"
    return citra, v["case_id"]


def propose(actor, case_id, label=None):
    r = actor.post(f"/api/cases/{case_id}/plan/propose", json={"selected_quote_label": label})
    assert r.status_code == 200, r.text
    plan = r.json()["plans"][-1]
    return {"plan_revision": plan["revision"], "plan_digest": plan["digest"]}


def test_no_session_cannot_read_or_approve(app):
    c = TestClient(app)
    assert c.get("/api/cases").status_code == 401
    r = c.post("/api/cases/case_0000000000000000/plan/approve",
               json={"plan_revision": 1, "plan_digest": "a" * 64}, headers={"Idempotency-Key": "k" * 16})
    assert r.status_code == 401


def test_expired_session_cannot_approve(login, samples, clock):
    citra, case_id = legit_case(login, samples)
    body = propose(citra, case_id)
    clock.advance(minutes=31)
    r = citra.post(f"/api/cases/{case_id}/plan/approve", json=body, headers={"Idempotency-Key": "expired-key-1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "session expired"


def test_forged_session_cookie_rejected(app):
    c = TestClient(app)
    c.cookies.set("cekbao_session", "forged-token-value")
    assert c.get("/api/session/me").status_code == 401


def test_missing_csrf_token_rejected(login, samples):
    citra = login("stu_citra")
    r = citra.client.post("/api/cases", json={"case_type": "tuition_request", "message": "x"})
    assert r.status_code == 403


def test_wrong_access_code_and_lockout(app):
    c = TestClient(app)
    for _ in range(5):
        assert c.post("/api/session/login", json={"user_id": "stu_ayu", "access_code": "wrong-code"}).status_code == 401
    r = c.post("/api/session/login", json={"user_id": "stu_ayu", "access_code": CODES["stu_ayu"]})
    assert r.status_code == 429


def test_cross_user_access_denied(login, samples):
    citra, case_id = legit_case(login, samples)
    ayu = login("stu_ayu")
    assert ayu.get(f"/api/cases/{case_id}").status_code == 404
    assert ayu.get(f"/api/cases/{case_id}/evidence.json").status_code == 404
    assert ayu.post(f"/api/cases/{case_id}/analyze").status_code == 404
    body = propose(citra, case_id)
    r = ayu.post(f"/api/cases/{case_id}/plan/approve", json=body, headers={"Idempotency-Key": "cross-user-1"})
    assert r.status_code == 404
    assert case_id not in [c["case_id"] for c in ayu.get("/api/cases").json()["cases"]]


def test_reviewer_cannot_approve_or_create(login, samples):
    citra, case_id = legit_case(login, samples)
    body = propose(citra, case_id)
    officer = login("officer_nbu")
    r = officer.post(f"/api/cases/{case_id}/plan/approve", json=body, headers={"Idempotency-Key": "officer-try-1"})
    assert r.status_code == 403
    r = officer.post("/api/cases", json={"case_type": "tuition_request", "message": "hello"})
    assert r.status_code == 403


def test_reviewer_sees_only_escalated_cases_of_own_institution(login, samples):
    ayu = login("stu_ayu")
    blocked = ayu.new_tuition_case(sample_by_id(samples, "A_SUSPICIOUS_INTL"))
    ayu.analyze(blocked["case_id"])
    citra, open_case = legit_case(login, samples)
    officer = login("officer_nbu")
    ids = [e["case_id"] for e in officer.get("/api/office/escalations").json()["escalations"]]
    assert blocked["case_id"] in ids and open_case not in ids
    assert officer.get(f"/api/cases/{open_case}").status_code == 404
    assert ayu.get("/api/office/escalations").status_code == 403


def test_client_cannot_inject_role_owner_or_approval_fields(login, samples):
    citra = login("stu_citra")
    s = sample_by_id(samples, "C_LEGITIMATE")
    r = citra.post("/api/cases", json={"case_type": "tuition_request", "message": s["message"],
                                      "owner_id": "stu_ayu", "role": "office_reviewer", "approved": True})
    assert r.status_code == 422
    citra2, case_id = legit_case(login, samples)
    body = propose(citra2, case_id)
    r = citra2.post(f"/api/cases/{case_id}/plan/approve", json={**body, "status": "approved", "role": "admin"},
                    headers={"Idempotency-Key": "inject-1234"})
    assert r.status_code == 422


def test_blocked_case_cannot_be_approved(login, samples):
    ayu = login("stu_ayu")
    case = ayu.new_tuition_case(sample_by_id(samples, "A_SUSPICIOUS_INTL"))
    v = ayu.analyze(case["case_id"])
    assert v["state"] == "blocked"
    r = ayu.post(f"/api/cases/{case['case_id']}/plan/propose", json={})
    assert r.status_code == 409
    r = ayu.post(f"/api/cases/{case['case_id']}/plan/approve", json={"plan_revision": 1, "plan_digest": "0" * 64},
                 headers={"Idempotency-Key": "blocked-1234"})
    assert r.status_code == 409
    assert "payment hold" in r.json()["detail"]


def test_duplicate_approval_executes_once(login, samples, app):
    citra, case_id = legit_case(login, samples)
    body = propose(citra, case_id)
    r1 = citra.post(f"/api/cases/{case_id}/plan/approve", json=body, headers={"Idempotency-Key": "same-key-0001"})
    r2 = citra.post(f"/api/cases/{case_id}/plan/approve", json=body, headers={"Idempotency-Key": "same-key-0001"})
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["plan_id"] == r2.json()["plan_id"]
    assert r1.json()["idempotent_replay"] is False and r2.json()["idempotent_replay"] is True
    r3 = citra.post(f"/api/cases/{case_id}/plan/approve", json=body, headers={"Idempotency-Key": "other-key-0002"})
    assert r3.status_code == 409
    view = citra.get(f"/api/cases/{case_id}").json()
    assert [e["event_type"] for e in view["audit_events"]].count("PLAN_APPROVED") == 1
    assert [p["status"] for p in view["plans"]].count("approved") == 1


def test_idempotency_key_reuse_with_different_body_rejected(login, samples):
    citra, case_id = legit_case(login, samples)
    body = propose(citra, case_id)
    citra.post(f"/api/cases/{case_id}/plan/approve", json=body, headers={"Idempotency-Key": "reuse-key-001"})
    r = citra.post(f"/api/cases/{case_id}/plan/approve", json={**body, "plan_revision": 2},
                   headers={"Idempotency-Key": "reuse-key-001"})
    assert r.status_code == 409


def test_approval_requires_idempotency_key(login, samples):
    citra, case_id = legit_case(login, samples)
    body = propose(citra, case_id)
    assert citra.post(f"/api/cases/{case_id}/plan/approve", json=body).status_code == 400


def test_stale_plan_digest_rejected(login, samples):
    citra, case_id = legit_case(login, samples)
    body = propose(citra, case_id)
    r = citra.post(f"/api/cases/{case_id}/plan/approve", json={**body, "plan_digest": "f" * 64},
                   headers={"Idempotency-Key": "stale-key-001"})
    assert r.status_code == 409


def test_user_rejection_preserves_state(login, samples):
    citra, case_id = legit_case(login, samples)
    before = citra.get(f"/api/cases/{case_id}").json()
    body = propose(citra, case_id)
    r = citra.post(f"/api/cases/{case_id}/plan/deny", json={**body, "reason": "not now"})
    assert r.status_code == 200
    after = r.json()
    assert after["state"] == "needs_review"
    assert after["analysis"] == before["analysis"]
    assert after["plans"][-1]["status"] == "denied"
    assert [e["event_type"] for e in after["audit_events"]][-1] == "PLAN_DENIED"
    # A new proposal is still possible after a denial.
    body2 = propose(citra, case_id)
    assert body2["plan_revision"] == 2


def test_edit_after_approval_requires_new_approval(login, samples):
    citra, case_id = legit_case(login, samples)
    body = propose(citra, case_id)
    assert citra.post(f"/api/cases/{case_id}/plan/approve", json=body,
                      headers={"Idempotency-Key": "edit-flow-001"}).status_code == 200
    body2 = propose(citra, case_id)  # edit creates revision 2
    view = citra.get(f"/api/cases/{case_id}").json()
    assert view["state"] == "needs_review"
    assert [p["status"] for p in view["plans"]] == ["superseded", "proposed"]
    assert "PLAN_EDITED" in [e["event_type"] for e in view["audit_events"]]
    assert citra.post(f"/api/cases/{case_id}/plan/approve", json=body,
                      headers={"Idempotency-Key": "edit-flow-002"}).status_code == 409
    assert citra.post(f"/api/cases/{case_id}/plan/approve", json=body2,
                      headers={"Idempotency-Key": "edit-flow-003"}).status_code == 200


def test_security_headers_and_cookie_flags(app):
    c = TestClient(app)
    r = c.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    r = c.post("/api/session/login", json={"user_id": "stu_ayu", "access_code": CODES["stu_ayu"]})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert r.headers["cache-control"] == "no-store"


def test_validation_errors_do_not_echo_input(login):
    ayu = login("stu_ayu")
    r = ayu.post("/api/cases", json={"case_type": "tuition_request", "message": "x", "secret_field": "TOPSECRET"})
    assert r.status_code == 422 and "TOPSECRET" not in r.text


def test_oversized_request_rejected(login):
    ayu = login("stu_ayu")
    r = ayu.post("/api/cases", json={"case_type": "tuition_request", "message": "x" * 2_100_000})
    assert r.status_code == 413


def _evidence_draft(login, samples):
    budi = login("stu_budi")
    s = sample_by_id(samples, "B_UMTS_INSPIRED")
    r = budi.post("/api/cases", json={"case_type": "payment_evidence", "institution_id": s["institution_id"],
                                     "offer_message": s["offer_message"], "slips": s["slips"]})
    assert r.status_code == 201, r.text
    return budi, r.json()["case_id"]


def test_pdf_receipt_claiming_paid_does_not_yield_paid(login, samples):
    budi, case_id = _evidence_draft(login, samples)
    pdf = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n(STATUS: PAID / LUNAS / PAYMENT SUCCESSFUL)\n%%EOF"
    r = budi.post(f"/api/cases/{case_id}/uploads", files={"file": ("bukti_LUNAS.pdf", pdf, "application/pdf")},
                  data={"slip_id": "TRX-SYN-0002"})
    assert r.status_code == 201, r.text
    assert r.json()["content_stored"] is False
    v = budi.analyze(case_id)
    slip = next(x for x in v["analysis"]["settlement"]["results"] if x["slip_id"] == "TRX-SYN-0002")
    assert slip["settlement_status"] == "PAYMENT_UNCONFIRMED"
    assert slip["next_action"] == "REQUIRES_INSTITUTION_CHECK"
    import json
    assert "PAID" not in json.dumps(v["analysis"]["settlement"])


def test_malicious_uploads_rejected(login, samples):
    budi, case_id = _evidence_draft(login, samples)
    cases = [
        ("slip.pdf.exe", b"MZ\x90\x00", 422),
        ("slip.exe.pdf", b"%PDF-1.4 x", 422),
        ("slip.pdf", b"MZ\x90\x00 not a pdf", 422),
        ("slip.pdf", b"%PDF-1.4 /OpenAction << /S /JavaScript /JS (app.alert(1)) >>", 422),
        ("slip.svg", b"<svg onload=alert(1)>", 422),
        ("big.png", b"\x89PNG\r\n\x1a\n" + b"0" * 1_000_001, 422),
        ("../../etc/passwd.txt", b"root:x:0:0", 201),
    ]
    for name, data, expected in cases:
        r = budi.post(f"/api/cases/{case_id}/uploads", files={"file": (name, data, "application/octet-stream")})
        assert r.status_code == expected, (name, r.text)
        if expected == 201:
            assert r.json()["safe_name"] == "passwd.txt"


def test_evidence_case_only_for_own_institution(login, samples):
    ayu = login("stu_ayu")
    s = sample_by_id(samples, "B_UMTS_INSPIRED")
    r = ayu.post("/api/cases", json={"case_type": "payment_evidence", "institution_id": "SYN-ID-UCN",
                                    "slips": s["slips"]})
    assert r.status_code == 403
