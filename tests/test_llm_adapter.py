"""LLM tool-calling adapter with a MOCK transport.

These tests verify the adapter protocol, schema validation, grounding and the
fallback path offline. They are NOT a live-model evaluation. No provider is
called and no API key is used.
"""
import json

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from conftest import Actor, sample_by_id

FAKE_KEY = "sk-test-NOT-A-REAL-KEY-0000"


def tool_call(name, args, cid="call_1"):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]}


GOOD_EXTRACTION = {
    "claimed_institution": "Northbridge University", "amount": "500.00", "currency": "USD",
    "beneficiary_name": "Northbridge University", "beneficiary_account": "[ACCOUNT_1]",
    "swift_bic": "SYNTUS33XXX", "bank_name": "Synthetic Trust Bank",
    "payment_methods": ["international_wire", "institution_portal"], "deadline_text": None,
}


class Recorder:
    def __init__(self, script):
        self.script = list(script)
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append({"headers": dict(request.headers), "body": body})
        return httpx.Response(200, json=self.script.pop(0))


def make_app(tmp_path, clock, recorder):
    s = Settings(db_path=tmp_path / "llm.sqlite3", clock=clock, pbkdf2_iterations=1000,
                 llm_base_url="https://llm.invalid/v1", llm_model="mock-model", llm_api_key=FAKE_KEY)
    return create_app(s, llm_transport=httpx.MockTransport(recorder))


def run_case(app, samples, sid, user):
    actor = Actor(app, user)
    case = actor.new_tuition_case(sample_by_id(samples, sid))
    return actor, actor.analyze(case["case_id"])


def test_tool_loop_lookup_then_submit(tmp_path, clock, samples):
    rec = Recorder([tool_call("lookup_institution", {"name": "Northbridge University"}),
                    tool_call("submit_extraction", GOOD_EXTRACTION, "call_2")])
    app = make_app(tmp_path, clock, rec)
    actor, v = run_case(app, samples, "C_LEGITIMATE", "stu_citra")
    ext = v["analysis"]["extraction"]
    assert ext["mode"] == "LLM_TOOL_CALLING"
    assert [t["tool"] for t in ext["tool_trace"]] == ["lookup_institution", "submit_extraction"]
    assert v["analysis"]["policy"]["overall_status"] == "MATCHED_SOURCE"
    # The tool result returned to the model is the read-only registry lookup.
    tool_msg = rec.requests[1]["body"]["messages"][-1]
    assert tool_msg["role"] == "tool" and json.loads(tool_msg["content"])["found"] is True


def test_model_sees_only_redacted_text(tmp_path, clock, samples):
    rec = Recorder([tool_call("submit_extraction", GOOD_EXTRACTION)])
    app = make_app(tmp_path, clock, rec)
    run_case(app, samples, "C_LEGITIMATE", "stu_citra")
    sent = json.dumps(rec.requests[0]["body"])
    for raw in ("000123456789", "student-accounts@northbridge-university.example", "citra.student@mail.example"):
        assert raw not in sent
    assert "[ACCOUNT_1]" in sent and "<untrusted_message>" in sent


def test_disallowed_tool_falls_back_and_cannot_approve(tmp_path, clock, samples):
    rec = Recorder([tool_call("approve_payment", {"case_id": "x"})])
    app = make_app(tmp_path, clock, rec)
    actor, v = run_case(app, samples, "D2_PROMPT_INJECTION", "stu_ayu")
    ext = v["analysis"]["extraction"]
    assert ext["mode"] == "DETERMINISTIC_FALLBACK_AFTER_LLM_ERROR"
    assert "allowlist" in ext["llm_error"]
    assert v["analysis"]["policy"]["decision"] == "HOLD_DO_NOT_PAY"
    assert v["state"] == "blocked"


def test_schema_violation_falls_back(tmp_path, clock, samples):
    bad = {**GOOD_EXTRACTION, "status": "MATCHED_SOURCE"}  # extra key
    rec = Recorder([tool_call("submit_extraction", bad)])
    app = make_app(tmp_path, clock, rec)
    _, v = run_case(app, samples, "C_LEGITIMATE", "stu_citra")
    assert v["analysis"]["extraction"]["mode"] == "DETERMINISTIC_FALLBACK_AFTER_LLM_ERROR"


def test_wrong_type_falls_back(tmp_path, clock, samples):
    bad = {**GOOD_EXTRACTION, "amount": 500.0}  # number instead of string
    rec = Recorder([tool_call("submit_extraction", bad)])
    app = make_app(tmp_path, clock, rec)
    _, v = run_case(app, samples, "C_LEGITIMATE", "stu_citra")
    assert v["analysis"]["extraction"]["mode"] == "DETERMINISTIC_FALLBACK_AFTER_LLM_ERROR"


def test_ungrounded_model_value_is_discarded(tmp_path, clock, samples):
    # The model invents an approved-looking payee for a scam message. Grounding drops it.
    hallucinated = {**GOOD_EXTRACTION, "beneficiary_name": "Northbridge University", "beneficiary_account": None,
                    "swift_bic": None}
    rec = Recorder([tool_call("submit_extraction", hallucinated)])
    app = make_app(tmp_path, clock, rec)
    _, v = run_case(app, samples, "A_SUSPICIOUS_INTL", "stu_ayu")
    ext = v["analysis"]["extraction"]
    assert ext["mode"] == "LLM_TOOL_CALLING"
    pol = v["analysis"]["policy"]
    payee = next(f for f in pol["findings"] if f["check_id"] == "BENEFICIARY_NAME")
    # "Northbridge University" does appear in the scam text (signature), so it is grounded; the deterministic
    # account, SWIFT and domain checks still produce CONFLICT and HOLD.
    assert pol["overall_status"] == "CONFLICT" and pol["decision"] == "HOLD_DO_NOT_PAY"
    assert payee["status"] in ("MATCHED_SOURCE", "CONFLICT")


def test_value_not_in_text_is_ungrounded(tmp_path, clock, samples):
    invented = {**GOOD_EXTRACTION, "bank_name": "Totally Invented Bank"}
    rec = Recorder([tool_call("submit_extraction", invented)])
    app = make_app(tmp_path, clock, rec)
    _, v = run_case(app, samples, "C_LEGITIMATE", "stu_citra")
    assert "bank_name" in v["analysis"]["extraction"]["ungrounded_fields"]
    assert any(s["signal_id"] == "UNGROUNDED_MODEL_OUTPUT" for s in v["analysis"]["policy"]["risk_signals"])


def test_provider_error_falls_back(tmp_path, clock, samples):
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})
    s = Settings(db_path=tmp_path / "e.sqlite3", clock=clock, pbkdf2_iterations=1000,
                 llm_base_url="https://llm.invalid/v1", llm_model="mock-model", llm_api_key=FAKE_KEY)
    app = create_app(s, llm_transport=httpx.MockTransport(handler))
    _, v = run_case(app, samples, "C_LEGITIMATE", "stu_citra")
    assert v["analysis"]["extraction"]["mode"] == "DETERMINISTIC_FALLBACK_AFTER_LLM_ERROR"
    assert "FALLBACK" in v["analysis"]["extraction"]["mode_label"]


def test_api_key_never_leaks(tmp_path, clock, samples, caplog):
    rec = Recorder([tool_call("submit_extraction", GOOD_EXTRACTION)])
    app = make_app(tmp_path, clock, rec)
    actor, v = run_case(app, samples, "C_LEGITIMATE", "stu_citra")
    assert rec.requests[0]["headers"]["authorization"] == f"Bearer {FAKE_KEY}"
    bundle = actor.get(f"/api/cases/{v['case_id']}/evidence.json").text
    html = actor.get(f"/api/cases/{v['case_id']}/evidence.html").text
    assert FAKE_KEY not in bundle and FAKE_KEY not in html and FAKE_KEY not in json.dumps(v)
    assert FAKE_KEY not in caplog.text
    assert FAKE_KEY not in repr(app.state.svc.settings) and FAKE_KEY not in repr(app.state.svc.llm)


def test_offline_mode_is_labeled(app, samples):
    from fastapi.testclient import TestClient
    assert TestClient(app).get("/api/health").json()["extraction_mode"] == "DETERMINISTIC_DEMO"
    actor = Actor(app, "stu_citra")
    case = actor.new_tuition_case(sample_by_id(samples, "C_LEGITIMATE"))
    v = actor.analyze(case["case_id"])
    ext = v["analysis"]["extraction"]
    assert ext["mode"] == "DETERMINISTIC_DEMO" and ext["llm_verified"] is False
    assert "No live model call was made" in ext["mode_label"]


@pytest.mark.parametrize("args", [{"name": ""}, {"name": "x" * 500}, {"name": "ok", "extra": 1}])
def test_lookup_tool_arguments_are_validated(tmp_path, clock, samples, args):
    rec = Recorder([tool_call("lookup_institution", args)])
    app = make_app(tmp_path, clock, rec)
    _, v = run_case(app, samples, "C_LEGITIMATE", "stu_citra")
    assert v["analysis"]["extraction"]["mode"] == "DETERMINISTIC_FALLBACK_AFTER_LLM_ERROR"
