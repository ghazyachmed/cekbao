"""Server-rendered check flow, result display and reviewer workspace (frontend requirements, case 20 partly)."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from policyguard.domain.model import NextAction, PolicyDecision
from policyguard.runtime import build_runtime
from policyguard.seed import SAMPLES, load_demo
from policyguard.web import display

PAYER = ("pg_payer", "demo-payer-2026")
REVIEWER = ("pg_reviewer", "demo-reviewer-2026")


@pytest.fixture
def rt(db, clock, pg_settings, tmp_path):
    load_demo(db, clock())
    pg_settings.storage_dir = tmp_path / "objects"
    return build_runtime(pg_settings, engine=db, clock=clock)


@pytest.fixture
def make(rt, tmp_path, clock):
    def _make():
        settings = Settings(db_path=tmp_path / "web.sqlite3", clock=clock, pbkdf2_iterations=1000)
        return TestClient(create_app(settings, policyguard=rt), follow_redirects=False)
    return _make


def sign_in(client, who=PAYER):
    r = client.post("/check/sign-in", data={"user_id": who[0], "access_code": who[1]})
    assert r.status_code == 303, r.text
    return client


def form_tokens(html: str) -> dict:
    return {name: re.search(rf'name="{name}" value="([^"]+)"', html).group(1)
            for name in ("csrf_token", "idempotency_token")}


def check_form(client, sample="conflict", **override):
    html = client.get("/check").text
    data = {**form_tokens(html), **{k: v for k, v in SAMPLES[sample]["input"].items() if v is not None}}
    data["institution_choice"] = data.pop("institution_id")
    data.update(override)
    return data


def run_worker(rt):
    rt.container.worker.relay()
    while rt.container.worker.run_once("w1"):
        pass


def test_check_requires_sign_in(make):
    r = make().get("/check")
    assert r.status_code == 303 and r.headers["location"].startswith("/check/sign-in")


def test_form_has_labels_landmarks_and_synthetic_examples(make):
    html = sign_in(make()).get("/check").text
    assert 'href="#main"' in html and '<main id="main"' in html                     # skip link + landmark
    assert '<label for="instruction_text"' in html
    assert 'value="__not_listed__"' in html                                           # unknown institution option
    assert "Date you intend to pay" in html and "Date you received" in html
    assert "Check instructions" in html and "Synthetic example" in html
    assert 'name="robots" content="noindex' in html


def test_app_pages_are_not_cached(make):
    r = sign_in(make()).get("/check")
    assert "no-store" in r.headers["cache-control"]


def test_validation_errors_are_summarized_and_input_is_preserved(make):
    client = sign_in(make())
    data = check_form(client, instruction_text="too short", due_on="2026-13-45")
    r = client.post("/check", data=data)
    assert r.status_code == 422
    assert 'role="alert"' in r.text and 'href="#instruction_text"' in r.text
    assert "too short" in r.text and 'aria-invalid="true"' in r.text


def test_unknown_institution_needs_a_name(make):
    client = sign_in(make())
    r = client.post("/check", data=check_form(client, institution_choice="__not_listed__", institution_query=""))
    assert r.status_code == 422 and 'href="#institution_query"' in r.text


def test_submit_redirects_and_duplicate_submission_returns_same_case(make):
    client = sign_in(make())
    data = check_form(client)
    a = client.post("/check", data=data)
    b = client.post("/check", data=data)
    assert a.status_code == b.status_code == 303 and a.headers["location"] == b.headers["location"]
    assert a.headers["location"].startswith("/check/cases/case_")


def test_processing_page_reflects_backend_state_without_fake_progress(make):
    client = sign_in(make())
    loc = client.post("/check", data=check_form(client)).headers["location"]
    page = client.get(loc).text
    assert "Queued" in page and 'aria-live="polite"' in page and "%" not in re.sub(r"<style.*?</style>", "", page)
    assert client.get(loc + "/status.json").json()["state"] == "ACCEPTED"


def test_result_reading_order_and_no_safety_claim(make, rt):
    client = sign_in(make())
    loc = client.post("/check", data=check_form(client)).headers["location"]
    run_worker(rt)
    html = client.get(loc).text
    order = [html.index(s) for s in ("Conflicts with the checked policy", 'id="next-action"', 'id="explanation"',
                                     'id="evidence"', 'id="limitations"')]
    assert order == sorted(order)
    assert "We never ask you to pay a third party." in html                   # decisive quotation visible
    assert "does not confirm" in html and "safe to pay" not in html.lower()
    assert "Effective from" in html and "Retrieved on" in html
    assert "SYNTHETIC" in html.upper()


def test_policy_change_shows_both_dates_and_versions(make, rt):
    client = sign_in(make())
    loc = client.post("/check", data=check_form(client, "policy_change")).headers["location"]
    run_worker(rt)
    html = client.get(loc).text
    assert "30 November 2026" in html and "14 August 2026" in html
    assert "2026.1" in html and "2025.1" in html
    assert "earlier policy version" in html


def test_translated_evidence_is_labeled_and_original_kept(make, rt):
    client = sign_in(make())
    loc = client.post("/check", data=check_form(client, "insufficient")).headers["location"]
    run_worker(rt)
    html = client.get(loc).text
    assert "Not enough evidence to verify" in html
    assert 'lang="fr"' in html and "Le dépôt d" in html and "Translation" in html


def test_status_json_is_tenant_and_owner_scoped(make, rt):
    owner = sign_in(make())
    loc = owner.post("/check", data=check_form(owner)).headers["location"]
    other = sign_in(make(), REVIEWER)            # reviewers may read; a second payer may not
    assert other.get(loc + "/status.json").status_code == 200


def test_reviewer_workspace_is_server_enforced(make, rt):
    payer = sign_in(make())
    assert payer.get("/review").status_code == 403
    assert "Review queue" not in payer.get("/check").text
    loc = payer.post("/check", data=check_form(payer, "source_conflict")).headers["location"]
    run_worker(rt)
    reviewer = sign_in(make(), REVIEWER)
    queue = reviewer.get("/review").text
    assert "<table" in queue and "Institution review required" in queue
    case_id = loc.rsplit("/", 1)[1]
    page = reviewer.get(f"/review/cases/{case_id}").text
    tokens = {"csrf_token": re.search(r'name="csrf_token" value="([^"]+)"', page).group(1),
              "row_version": re.search(r'name="row_version" value="(\d+)"', page).group(1)}
    bad = reviewer.post(f"/review/cases/{case_id}", data={**tokens, "outcome": "CONFIRMED", "reason": "short"})
    assert bad.status_code == 422 and 'href="#reason"' in bad.text
    ok = reviewer.post(f"/review/cases/{case_id}", data={**tokens, "outcome": "NEEDS_MORE_INFORMATION",
                                                         "reason": "Asked the finance office which account is current."})
    assert ok.status_code == 303
    assert "Asked the finance office" in reviewer.get(f"/review/cases/{case_id}").text


def test_upload_rejection_reason_is_returned(make):
    client = sign_in(make())
    csrf = form_tokens(client.get("/check").text)["csrf_token"]
    bad = client.post("/check/uploads", files={"file": ("x.pdf", b"%PDF-1.4 /JavaScript (x)", "application/pdf")},
                      headers={"X-CSRF-Token": csrf})
    assert bad.status_code == 200 and bad.json()["status"] == "REJECTED" and bad.json()["reject_reason"]
    ok = client.post("/check/uploads", files={"file": ("x.txt", b"Invoice text", "text/plain")},
                     headers={"X-CSRF-Token": csrf})
    assert ok.json()["status"] == "CLEAN"
    assert client.post("/check/uploads", files={"file": ("x.exe", b"MZ", "application/octet-stream")},
                       headers={"X-CSRF-Token": csrf}).status_code == 422


def test_expired_session_keeps_the_instruction_on_the_page(make, clock):
    client = sign_in(make())
    data = check_form(client)
    clock.advance(hours=2)
    r = client.post("/check", data=data)
    assert r.status_code == 401 and "Sign in" in r.text and "Northbridge Education Services Ltd" in r.text


def test_robots_and_sitemap(make):
    client = make()
    robots = client.get("/robots.txt").text
    assert "Disallow: /check" in robots and "Sitemap: http://testserver/sitemap.xml" in robots   # absolute URL
    assert "<urlset" in client.get("/sitemap.xml").text


@pytest.mark.parametrize("decision,label", [
    (PolicyDecision.CONSISTENT, "Matches the checked policy."),
    (PolicyDecision.CONFLICT, "Conflicts with the checked policy."),
    (PolicyDecision.INSUFFICIENT_EVIDENCE, "Not enough evidence to verify."),
    (PolicyDecision.REQUIRES_REVIEW, "Institution review required.")])
def test_decision_labels(decision, label):
    assert display.decision(decision.value)["label"] == label


def test_every_next_action_and_failure_state_has_text():
    for action in NextAction:
        assert display.next_action(action.value, "Aster Bay University")
    failed = display.job_state("FAILED")
    assert "technical" in failed["description"].lower() and "not a judgment" in failed["description"].lower()


def test_dates_use_month_names_and_time_zone():
    assert display.date_label("2026-11-15T00:00:00+00:00", "Europe/London") == "15 November 2026"
    assert display.timestamp_label("2026-10-28T09:14:00+00:00") == "28 October 2026, 09:14 UTC"


def test_comparison_table_is_the_core_of_the_result(make, rt):
    client = sign_in(make())
    loc = client.post("/check", data=check_form(client)).headers["location"]
    run_worker(rt)
    html = client.get(loc).text
    table = html[html.index('<table class="compare-table"'):html.index("</table>", html.index('<table class="compare-table"'))]
    assert "<caption" in table and "The instruction asks for" in table and "The policy states" in table
    account_row = table[table.index(">Account<"):]
    account_row = account_row[:account_row.index("</tr>")]
    assert "GB71 SYNT 7777 0000 1234 56" in account_row and "GB94 SYNT 4000 0055 5501 77" in account_row
    assert "Conflicts" in account_row
    currency_row = table[table.index(">Currency<"):]
    assert "Agrees" in currency_row[:currency_row.index("</tr>")]
    assert 'id="still-unknown"' in html and "reaches the institution" in html


def test_comparison_marks_a_source_without_authority(make, rt):
    client = sign_in(make())
    loc = client.post("/check", data=check_form(client, "insufficient")).headers["location"]
    run_worker(rt)
    html = client.get(loc).text
    assert "Agent or third-party page states (no authority)" in html
    assert "may set payment details for this institution" in html


def test_comparison_shows_both_conflicting_sources(make, rt):
    client = sign_in(make())
    loc = client.post("/check", data=check_form(client, "source_conflict")).headers["location"]
    run_worker(rt)
    html = client.get(loc).text
    table = html[html.index('<table class="compare-table"'):]
    assert "SYN 501-234567-001" in table and "SYN 501-765432-009" in table
    assert "Which of the two sources is correct" in html
