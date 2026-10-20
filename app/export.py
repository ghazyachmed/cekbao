"""Reproducible evidence bundle (JSON and HTML).

The bundle holds no export timestamp. Two exports of the same case state give
identical bytes. Export requests go to the access log, not to the case audit
chain, so an export does not change the next export.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import audit
from .auth import Session
from .workflow import SANDBOX_NOTICE, Services, case_view

LIMITATIONS = [
    "MATCHED_SOURCE means the request fields match the curated registry entry. It is not bank-level payee "
    "authentication.",
    "A slip, receipt or screenshot is a document claim. Only an institution-side record confirms settlement.",
    "All institutions, accounts, ledgers, bank feeds and quotes in this sandbox are synthetic or user-provided.",
    "FX figures are user-provided illustrative quotes. CEKBAO did not fetch live market rates.",
    "CEKBAO gives no legal, visa or investment advice and executes no payments.",
]

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                   autoescape=select_autoescape(["html"]))


def _recommendation(view: dict) -> str:
    a = view["analysis"] or {}
    pol = a.get("policy") or {}
    contact = ((a.get("institution") or {}).get("official_contact") or {})
    if view["case_type"] == "payment_evidence":
        s = a.get("settlement") or {}
        return (f"{s.get('slips_confirmed_by_institution_ledger', 0)} of {s.get('slips_submitted', 0)} slip(s) match "
                f"an institution ledger record. Unconfirmed: {s.get('slips_unconfirmed', 0)} "
                f"(REQUIRES_INSTITUTION_CHECK). Conflicts: {s.get('slips_in_conflict', 0)}. "
                f"Make no further payment through the intermediary. Contact {contact.get('office', 'the finance office')} "
                f"through the registry contact.")
    if pol.get("decision") == "HOLD_DO_NOT_PAY":
        who = contact.get("office") or "the institution finance office (find the contact yourself)"
        return f"Do not pay through this request. Verify it with {who}. Use the draft and checklist."
    if view["state"] == "approved":
        return ("The student approved a sandbox payment plan. It is NOT executed. Pay only inside the official "
                "portal after you confirm the invoice amount.")
    if pol.get("decision") == "PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION":
        return ("The request matches the registry entry. Confirm the amount on your portal invoice. A sandbox plan "
                "needs your explicit approval.")
    return "Run the analysis first."


def _sources(view: dict) -> list[str]:
    urls: set[str] = set()
    a = view["analysis"] or {}
    for key in ("policy", "offer_policy"):
        pol = a.get(key) or {}
        for f in pol.get("findings", []):
            if f.get("source_url"):
                urls.add(f["source_url"])
        for s in pol.get("risk_signals", []):
            if s.get("source_url"):
                urls.add(s["source_url"])
    inst = a.get("institution") or {}
    for k in ("source_url",):
        if inst.get(k):
            urls.add(inst[k])
    if inst.get("official_contact", {}).get("contact_page_url"):
        urls.add(inst["official_contact"]["contact_page_url"])
    return sorted(urls)


def build_bundle(conn, svc: Services, session: Session, case_id: str) -> dict:
    view = case_view(conn, svc, session, case_id)
    events = audit.list_events(conn, case_id)
    a = view["analysis"] or {}
    pol = a.get("policy") or {}
    bundle = {
        "bundle_version": "1.0",
        "product": "CEKBAO | Student Payment Verification Agent",
        "sandbox_notice": SANDBOX_NOTICE,
        "synthetic_data_notice": svc.registry.notice,
        "case": {k: view[k] for k in ("case_id", "case_type", "state", "created_at", "updated_at")},
        "sanitized_request": view["input"],
        "extraction": a.get("extraction"),
        "institution": a.get("institution"),
        "registry": a.get("registry"),
        "overall_status": pol.get("overall_status"),
        "decision": pol.get("decision"),
        "reasons": pol.get("reasons", []),
        "findings": pol.get("findings", []),
        "risk_signals": pol.get("risk_signals", []),
        "offer_policy": a.get("offer_policy"),
        "settlement": a.get("settlement"),
        "quote_comparison": view["quotes"],
        "plans": view["plans"],
        "recommendation": _recommendation(view),
        "escalation": a.get("escalation"),
        "sources_cited": _sources(view),
        "audit_events": [{k: e[k] for k in ("event_id", "seq", "event_type", "at", "actor_id", "payload", "hash")}
                         for e in events],
        "audit_chain_valid": audit.verify_chain(events),
        "as_of_event_id": events[-1]["event_id"] if events else None,
        "limitations": LIMITATIONS,
    }
    bundle["bundle_sha256"] = hashlib.sha256(audit.canonical(bundle).encode()).hexdigest()
    return bundle


def bundle_json_bytes(bundle: dict) -> bytes:
    return audit.canonical(bundle).encode()


def render_html(bundle: dict) -> str:
    return _env.get_template("evidence.html").render(b=bundle)
