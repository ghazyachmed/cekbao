"""Case workflow: draft -> needs_review -> approved | blocked.

Every permission check and state transition happens here, on the server.
Client fields never carry roles, owners, approvals or statuses.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from . import audit
from .auth import Session
from .config import Settings
from .escalation import build_escalation
from .extractor import extract_deterministic
from .llm import LLMExtractor, LLMProtocolError, ground_value
from .models import (CaseState, CheckStatus, Decision, ExtractedRequest, ExtractionMode, Finding, PaymentMethod,
                     PolicyResult, RiskSignal, Severity)
from .money import QuoteError, QuoteInput, ReferenceRate, compare_quotes
from .policy import evaluate_request
from .registry import Registry
from .sanitize import InputRejected, detect_injection, mask_account, mask_phone, redact, sanitize_text
from .settlement import BankFeedTool, LedgerTool, SlipInput, reconcile
from .uploads import inspect_upload

MODE_LABELS = {
    ExtractionMode.DETERMINISTIC_DEMO: ("DETERMINISTIC DEMO MODE: no LLM is configured. A regex extractor read the "
                                        "message. No live model call was made."),
    ExtractionMode.LLM_TOOL_CALLING: ("LLM TOOL-CALLING MODE: a configured model proposed fields from the redacted "
                                      "message. Deterministic code validated them and decided every status."),
    ExtractionMode.DETERMINISTIC_FALLBACK_AFTER_LLM_ERROR: ("FALLBACK: the configured LLM call failed validation or "
                                                            "transport. The regex extractor was used instead."),
}
SANDBOX_NOTICE = ("SANDBOX PROTOTYPE. CEKBAO does not move money, connect to banks, authenticate payees against a bank "
                  "registry or send e-mail. All institutions, accounts, ledgers and bank feeds are SYNTHETIC.")


class WorkflowError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass
class Services:
    settings: Settings
    registry: Registry
    ledger: LedgerTool
    bank: BankFeedTool
    llm: LLMExtractor | None = None

    def now(self) -> datetime:
        return self.settings.clock()


class CreateTuitionCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_type: Literal["tuition_request"]
    claimed_institution: str | None = Field(default=None, max_length=120)
    message: str = Field(min_length=1, max_length=20_000)


class CreateEvidenceCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_type: Literal["payment_evidence"]
    institution_id: str = Field(pattern=r"^[A-Z0-9-]{3,40}$")
    offer_message: str | None = Field(default=None, max_length=20_000)
    slips: list[SlipInput] = Field(min_length=1, max_length=30)


CreateCase = Annotated[Union[CreateTuitionCase, CreateEvidenceCase], Field(discriminator="case_type")]


class QuotesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quotes: list[QuoteInput] = Field(min_length=2, max_length=3)
    reference_rate: ReferenceRate | None = None


class ProposePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_quote_label: str | None = Field(default=None, max_length=60)


class PlanDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_revision: int = Field(ge=1, le=1000)
    plan_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str | None = Field(default=None, max_length=300)


@contextmanager
def tx(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def _digest(obj) -> str:
    return hashlib.sha256(audit.canonical(obj).encode()).hexdigest()


# ---------------------------------------------------------------- loading


def _load_case(conn: sqlite3.Connection, session: Session, case_id: str, *, write: bool) -> sqlite3.Row:
    """Owner-scoped load. Office reviewers get read-only access to escalated cases of their institution."""
    if not re.fullmatch(r"case_[a-f0-9]{16}", case_id or ""):
        raise WorkflowError(404, "case not found")
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    u = session.user
    if row is None:
        raise WorkflowError(404, "case not found")
    if u.role == "student" and row["owner_id"] == u.user_id:
        return row
    if not write and u.role == "office_reviewer" and row["escalated"] and row["institution_id"] == u.institution_id:
        return row
    # Same answer as a missing case. Do not reveal that the case exists.
    raise WorkflowError(404, "case not found")


def _require_student(session: Session) -> None:
    if session.user.role != "student":
        raise WorkflowError(403, "only the student who owns the case can do this")


# ---------------------------------------------------------------- create


def create_case(conn: sqlite3.Connection, svc: Services, session: Session, payload) -> dict:
    _require_student(session)
    now = svc.now()
    case_id = "case_" + secrets.token_hex(8)
    if isinstance(payload, CreateTuitionCase):
        try:
            san = sanitize_text(payload.message, svc.settings.max_message_chars)
        except InputRejected as exc:
            raise WorkflowError(422, str(exc)) from None
        stored = {"claimed_institution": payload.claimed_institution, "sanitized_text": san.text,
                  "sanitize_flags": san.flags}
        institution_id = None
    else:
        entry = svc.registry.get(payload.institution_id)
        if entry is None:
            raise WorkflowError(422, "institution is not in the registry. Contact the institution directly.")
        if entry.institution_id != session.user.institution_id:
            raise WorkflowError(403, "you can check evidence only for your own institution")
        flags: list[str] = []
        text = None
        if payload.offer_message:
            try:
                san = sanitize_text(payload.offer_message, svc.settings.max_message_chars)
            except InputRejected as exc:
                raise WorkflowError(422, str(exc)) from None
            text, flags = san.text, san.flags
        stored = {"institution_id": entry.institution_id, "offer_text": text, "sanitize_flags": flags,
                  "slips": [s.model_dump(mode="json") for s in payload.slips]}
        institution_id = entry.institution_id
    with tx(conn):
        conn.execute(
            "INSERT INTO cases (case_id, owner_id, case_type, institution_id, state, created_at, updated_at, "
            "input_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (case_id, session.user.user_id, payload.case_type, institution_id, CaseState.DRAFT.value,
             now.isoformat(timespec="seconds"), now.isoformat(timespec="seconds"), json.dumps(stored)))
        audit.append_event(conn, case_id, session.user.user_id, "CASE_CREATED",
                           {"case_type": payload.case_type, "sanitize_flags": stored["sanitize_flags"]}, now)
    return case_view(conn, svc, session, case_id)


# ---------------------------------------------------------------- analyze


def _extract(svc: Services, text: str, claimed: str | None) -> tuple[ExtractedRequest, dict, list[str], dict]:
    red = redact(text)
    det = extract_deterministic(text, claimed, svc.registry)
    meta = {"mode": ExtractionMode.DETERMINISTIC_DEMO.value, "model": None, "llm_verified": False,
            "tool_trace": [], "redacted_placeholders": sorted({k.split("_")[0].strip("[") for k in red.mapping})}
    ungrounded: list[str] = []
    if svc.llm is None:
        return det, meta, ungrounded, red.mapping
    try:
        out = svc.llm.extract(red.text)
    except LLMProtocolError as exc:
        meta.update(mode=ExtractionMode.DETERMINISTIC_FALLBACK_AFTER_LLM_ERROR.value, llm_error=str(exc))
        return det, meta, ungrounded, red.mapping
    merged = det.model_dump()
    llm_fields = out.extraction.model_dump()
    for name in ("claimed_institution", "amount", "currency", "beneficiary_name", "beneficiary_account",
                 "swift_bic", "bank_name", "deadline_text"):
        val = llm_fields.get(name)
        if val is None:
            continue
        if name == "claimed_institution" and claimed:
            continue  # the student's own entry wins
        if name in ("currency",):
            merged[name] = val
            continue
        grounded_val, ok = ground_value(val, text, red.mapping)
        if ok:
            merged[name] = re.sub(r"[\s-]", "", grounded_val) if name == "beneficiary_account" else grounded_val
        else:
            ungrounded.append(name)
    methods = list(dict.fromkeys([*det.payment_methods, *[PaymentMethod(m) for m in llm_fields["payment_methods"]]]))
    merged["payment_methods"] = methods
    meta.update(mode=ExtractionMode.LLM_TOOL_CALLING.value, model=out.model, steps=out.steps,
                tool_trace=out.tool_trace, ungrounded_fields=ungrounded)
    return ExtractedRequest.model_validate(merged), meta, ungrounded, red.mapping


def _intermediary_hash(institution_id: str | None, phones: list[str]) -> str | None:
    if not phones:
        return None
    digits = re.sub(r"\D", "", phones[0])[-10:]
    return hashlib.sha256(f"{institution_id}|{digits}".encode()).hexdigest()


def _public_extraction(ex: ExtractedRequest) -> dict:
    d = ex.model_dump(mode="json")
    d["beneficiary_account"] = mask_account(ex.beneficiary_account)
    d["contact_phones"] = [mask_phone(p) for p in ex.contact_phones]
    d["sender_email"] = (("***@" + ex.sender_domain) if ex.sender_domain else None)
    return d


def analyze_case(conn: sqlite3.Connection, svc: Services, session: Session, case_id: str) -> dict:
    _require_student(session)
    row = _load_case(conn, session, case_id, write=True)
    if row["state"] != CaseState.DRAFT.value:
        raise WorkflowError(409, f"case is already analysed (state {row['state']})")
    now = svc.now()
    stored = json.loads(row["input_json"])
    if row["case_type"] == "tuition_request":
        return _analyze_tuition(conn, svc, session, row, stored, now)
    return _analyze_evidence(conn, svc, session, row, stored, now)


def _duplicate_intermediary(conn, owner_id: str, case_id: str, ihash: str | None) -> int:
    if not ihash:
        return 0
    return conn.execute("SELECT COUNT(*) FROM cases WHERE owner_id = ? AND intermediary_hash = ? AND case_id != ?",
                        (owner_id, ihash, case_id)).fetchone()[0]


def _analyze_tuition(conn, svc: Services, session: Session, row, stored: dict, now: datetime) -> dict:
    text = stored["sanitized_text"]
    injection = detect_injection(text)
    ex, meta, ungrounded, mapping = _extract(svc, text, stored.get("claimed_institution"))
    entry = svc.registry.resolve(ex.claimed_institution)
    result = evaluate_request(ex, entry, text, stored["sanitize_flags"], injection, ungrounded)
    ihash = _intermediary_hash(entry.institution_id if entry else None, ex.contact_phones)
    dup = _duplicate_intermediary(conn, row["owner_id"], row["case_id"], ihash)
    if dup:
        result.risk_signals.append(RiskSignal(
            signal_id="DUPLICATE_INTERMEDIARY_REQUEST", severity=Severity.HIGH,
            evidence=f"same contact in {dup} earlier case(s)",
            explanation="The same intermediary contact sent you more than one payment request.", source_url=None))
        result.decision = Decision.HOLD_DO_NOT_PAY
        result.reasons.append("RISK DUPLICATE_INTERMEDIARY_REQUEST")
    escalation = build_escalation(entry, result, row["case_id"], now.date().isoformat())
    state = (CaseState.NEEDS_REVIEW if result.decision is Decision.PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION
             else CaseState.BLOCKED)
    analysis = {
        "extraction": {**meta, "mode_label": MODE_LABELS[ExtractionMode(meta["mode"])],
                       "fields": _public_extraction(ex)},
        "institution": _institution_public(entry),
        "policy": result.model_dump(mode="json"),
        "escalation": escalation,
        "registry": {"version": svc.registry.version, "sha256": svc.registry.sha256},
        "invoice": {"amount": ex.amount, "currency": ex.currency,
                    "note": "Amount as stated in the request. Unverified until it matches your portal invoice."},
        "allowed_channel_ids": _allowed_channels(entry, ex),
    }
    redacted = redact(text).text
    new_input = {"claimed_institution": stored.get("claimed_institution"), "redacted_text": redacted,
                 "sanitize_flags": stored["sanitize_flags"]}
    with tx(conn):
        conn.execute(
            "UPDATE cases SET state = ?, institution_id = ?, analysis_json = ?, input_json = ?, escalated = ?, "
            "intermediary_hash = ?, updated_at = ? WHERE case_id = ?",
            (state.value, entry.institution_id if entry else None, json.dumps(analysis), json.dumps(new_input),
             int(state is CaseState.BLOCKED), ihash, now.isoformat(timespec="seconds"), row["case_id"]))
        uid = session.user.user_id
        audit.append_event(conn, row["case_id"], uid, "EXTRACTION_COMPLETED",
                           {"mode": meta["mode"], "model": meta.get("model"), "tool_trace": meta.get("tool_trace"),
                            "ungrounded_fields": ungrounded, "llm_error": meta.get("llm_error")}, now)
        audit.append_event(conn, row["case_id"], uid, "ANALYSIS_COMPLETED",
                           {"overall_status": result.overall_status.value, "decision": result.decision.value,
                            "findings_digest": _digest(analysis["policy"]),
                            "registry_sha256": svc.registry.sha256}, now)
        if state is CaseState.BLOCKED:
            audit.append_event(conn, row["case_id"], "system", "PAYMENT_HOLD",
                               {"reasons": result.reasons[:20]}, now)
        audit.append_event(conn, row["case_id"], "system", "ESCALATION_DRAFTED",
                           {"to": (escalation["draft_email"] or {}).get("to"), "auto_send": False}, now)
    return case_view(conn, svc, session, row["case_id"])


def _analyze_evidence(conn, svc: Services, session: Session, row, stored: dict, now: datetime) -> dict:
    entry = svc.registry.get(stored["institution_id"])
    slips = [SlipInput.model_validate(s) for s in stored["slips"]]
    offer = None
    offer_ex = None
    if stored.get("offer_text"):
        text = stored["offer_text"]
        offer_ex, meta, ungrounded, _ = _extract(svc, text, entry.display_name)
        offer = evaluate_request(offer_ex, entry, text, stored["sanitize_flags"], detect_injection(text), ungrounded)
    hashes = {s.slip_id: hashlib.sha256(f"{entry.institution_id}|{s.slip_id}".encode()).hexdigest() for s in slips}
    seen_rows = conn.execute(
        f"SELECT slip_hash FROM slip_index WHERE case_id != ? AND slip_hash IN ({','.join('?' * len(hashes))})",
        (row["case_id"], *hashes.values())).fetchall()
    seen_hashes = {r["slip_hash"] for r in seen_rows}
    previously_seen = {sid for sid, h in hashes.items() if h in seen_hashes}
    uploads: dict[str, list[dict]] = {}
    for u in conn.execute("SELECT * FROM uploads WHERE case_id = ? ORDER BY created_at", (row["case_id"],)):
        uploads.setdefault(u["slip_id"], []).append(dict(u))
    recon = reconcile(slips, entry, session.user.payer_reference or "", svc.ledger, svc.bank, previously_seen,
                      uploads, now.date())

    findings: list[Finding] = []
    for r in recon["results"]:
        if r["settlement_status"] == "CONFIRMED_BY_INSTITUTION_LEDGER":
            continue
        status = CheckStatus.CONFLICT if r["settlement_status"] == "CONFLICT" else CheckStatus.NOT_VERIFIABLE
        findings.append(Finding(
            check_id="SLIP", label=f"Slip {r['slip_id']}", status=status, required=True,
            observed=r["claimed_amount"],
            expected="matching institution ledger record",
            explanation=(f"{r['settlement_status']}, next action {r['next_action']}. "
                         + (" ".join(i["detail"] for i in r["issues"]) if r["issues"] else
                            "No institution ledger record matches this slip. A slip is not proof of settlement. "
                            "Ask the finance office through the registry contact.")),
            source_url=entry.source.url, source_synthetic=True))
    signals = list(offer.risk_signals) if offer else []
    if offer:
        findings = [f for f in offer.findings if f.status is CheckStatus.CONFLICT] + findings
    ihash = _intermediary_hash(entry.institution_id, offer_ex.contact_phones if offer_ex else [])
    dup = _duplicate_intermediary(conn, row["owner_id"], row["case_id"], ihash)
    if dup:
        signals.append(RiskSignal(
            signal_id="DUPLICATE_INTERMEDIARY_REQUEST", severity=Severity.HIGH,
            evidence=f"same contact in {dup} earlier case(s)",
            explanation="The same intermediary contact sent you more than one payment request.", source_url=None))
    hold = bool(findings) or any(s.severity is Severity.HIGH for s in signals)
    combined = PolicyResult(
        overall_status=(CheckStatus.CONFLICT if any(f.status is CheckStatus.CONFLICT for f in findings)
                        else CheckStatus.NOT_VERIFIABLE if findings else CheckStatus.MATCHED_SOURCE),
        decision=Decision.HOLD_DO_NOT_PAY,
        findings=findings, risk_signals=signals,
        reasons=[f"{f.label}: {f.status.value}" for f in findings])
    escalation = build_escalation(entry, combined, row["case_id"], now.date().isoformat(),
                                  kind="tuition payment offer and payment slips")
    state = CaseState.BLOCKED if hold else CaseState.NEEDS_REVIEW
    analysis = {
        "extraction": ({"mode": ExtractionMode.DETERMINISTIC_DEMO.value if svc.llm is None else "SEE_AUDIT",
                        "mode_label": MODE_LABELS[ExtractionMode.DETERMINISTIC_DEMO] if svc.llm is None else
                        "See audit log for the extraction mode.", "fields": _public_extraction(offer_ex)}
                       if offer_ex else None),
        "institution": _institution_public(entry),
        "offer_policy": offer.model_dump(mode="json") if offer else None,
        "settlement": recon,
        "policy": combined.model_dump(mode="json"),
        "escalation": escalation,
        "registry": {"version": svc.registry.version, "sha256": svc.registry.sha256},
    }
    new_input = dict(stored)
    # Keep only masked account numbers after the reconciliation (minimal retention).
    new_input["slips"] = [{**sl, "destination_account": mask_account(sl["destination_account"])}
                          for sl in stored["slips"]]
    if stored.get("offer_text"):
        new_input["offer_text"] = None
        new_input["redacted_offer_text"] = redact(stored["offer_text"]).text
    with tx(conn):
        conn.execute(
            "UPDATE cases SET state = ?, analysis_json = ?, input_json = ?, escalated = ?, intermediary_hash = ?, "
            "updated_at = ? WHERE case_id = ?",
            (state.value, json.dumps(analysis), json.dumps(new_input), int(hold), ihash,
             now.isoformat(timespec="seconds"), row["case_id"]))
        for h in hashes.values():
            conn.execute("INSERT OR IGNORE INTO slip_index (slip_hash, case_id) VALUES (?, ?)", (h, row["case_id"]))
        uid = session.user.user_id
        audit.append_event(conn, row["case_id"], uid, "SETTLEMENT_CHECKED", {
            "slips": len(slips), "confirmed": recon["slips_confirmed_by_institution_ledger"],
            "unconfirmed": recon["slips_unconfirmed"], "conflict": recon["slips_in_conflict"],
            "statuses": {r["slip_id"]: r["settlement_status"] for r in recon["results"]}}, now)
        if hold:
            audit.append_event(conn, row["case_id"], "system", "PAYMENT_HOLD", {"reasons": combined.reasons[:20]}, now)
        audit.append_event(conn, row["case_id"], "system", "ESCALATION_DRAFTED",
                           {"to": (escalation["draft_email"] or {}).get("to"), "auto_send": False}, now)
    return case_view(conn, svc, session, row["case_id"])


def _institution_public(entry) -> dict | None:
    if entry is None:
        return None
    return {"institution_id": entry.institution_id, "display_name": entry.display_name,
            "synthetic": entry.synthetic, "country": entry.country, "source_url": entry.source.url,
            "retrieved": entry.source.retrieved.isoformat(), "reviewed_by": entry.source.reviewed_by,
            "official_contact": entry.official_contact.model_dump()}


def _allowed_channels(entry, ex: ExtractedRequest) -> list[str]:
    if entry is None:
        return []
    methods = {m.value for m in ex.payment_methods}
    picked = [c.channel_id for c in entry.approved_channels if c.method in methods]
    return picked or [c.channel_id for c in entry.approved_channels if c.method == "institution_portal"]


# ---------------------------------------------------------------- quotes


def submit_quotes(conn, svc: Services, session: Session, case_id: str, req: QuotesRequest) -> dict:
    _require_student(session)
    row = _load_case(conn, session, case_id, write=True)
    if row["case_type"] != "tuition_request" or row["state"] == CaseState.DRAFT.value:
        raise WorkflowError(409, "quotes need an analysed tuition-request case")
    analysis = json.loads(row["analysis_json"])
    inv = analysis["invoice"]
    invoice_amount = Decimal(inv["amount"]) if inv.get("amount") else None
    now = svc.now()
    try:
        cmp = compare_quotes(req.quotes, invoice_amount, inv.get("currency"), now.date(), req.reference_rate)
    except QuoteError as exc:
        with tx(conn):
            audit.append_event(conn, case_id, session.user.user_id, "QUOTES_REJECTED", {"reason": str(exc)[:200]}, now)
        raise WorkflowError(422, str(exc)) from None
    data = cmp.model_dump(mode="json")
    data["invoice_note"] = inv["note"]
    with tx(conn):
        conn.execute("UPDATE cases SET quotes_json = ?, updated_at = ? WHERE case_id = ?",
                     (json.dumps(data), now.isoformat(timespec="seconds"), case_id))
        audit.append_event(conn, case_id, session.user.user_id, "QUOTES_COMPARED",
                           {"digest": _digest(data), "lowest_cost_covering_invoice":
                            data["lowest_cost_covering_invoice"]}, now)
    return case_view(conn, svc, session, case_id)


# ---------------------------------------------------------------- plan


def _current_plan(conn, case_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM plans WHERE case_id = ? ORDER BY revision DESC LIMIT 1", (case_id,)).fetchone()


def propose_plan(conn, svc: Services, session: Session, case_id: str, req: ProposePlanRequest) -> dict:
    _require_student(session)
    row = _load_case(conn, session, case_id, write=True)
    if row["case_type"] != "tuition_request":
        raise WorkflowError(409, "payment plans exist only for tuition-request cases")
    analysis = json.loads(row["analysis_json"] or "null")
    if row["state"] == CaseState.BLOCKED.value or not analysis or \
            analysis["policy"]["decision"] != Decision.PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION.value:
        raise WorkflowError(409, "payment hold: the policy decision does not allow a payment plan")
    if row["state"] not in (CaseState.NEEDS_REVIEW.value, CaseState.APPROVED.value):
        raise WorkflowError(409, f"cannot propose a plan in state {row['state']}")
    entry = svc.registry.get(row["institution_id"])
    quote = None
    if req.selected_quote_label:
        quotes = json.loads(row["quotes_json"] or "null")
        match = [q for q in (quotes or {}).get("results", []) if q["provider_label"] == req.selected_quote_label]
        if not match:
            raise WorkflowError(422, "selected quote not found. Submit quotes first.")
        if not match[0]["covers_invoice"]:
            raise WorkflowError(422, "selected quote does not deliver the full invoice amount")
        quote = match[0]
    channel = next(c for c in entry.approved_channels if c.channel_id in analysis["allowed_channel_ids"])
    plan = {
        "plan_type": "SANDBOX_PAYMENT_PLAN",
        "execution": "NOT_EXECUTED. CEKBAO has no bank connection and moves no money.",
        "institution_id": entry.institution_id,
        "institution_synthetic": entry.synthetic,
        "channel": {"channel_id": channel.channel_id, "method": channel.method,
                    "beneficiary_name": channel.beneficiary_name, "payment_host": channel.payment_host,
                    "account_masked": mask_account(channel.beneficiary_account), "swift_bic": channel.swift_bic,
                    "source_url": entry.source.url,
                    "note": "Channel details come from the registry, not from the pasted message."},
        "invoice": analysis["invoice"],
        "quote": quote,
        "student_steps": [
            "Open the official portal by typing its address yourself.",
            "Confirm the amount on your portal invoice before paying.",
            "Pay through the channel above with the student reference from your invoice.",
            "Keep the institution receipt. A bank slip alone is not proof that the institution received funds.",
        ],
    }
    digest = _digest(plan)
    now = svc.now()
    with tx(conn):
        prev = _current_plan(conn, case_id)
        revision = (prev["revision"] + 1) if prev else 1
        if prev and prev["status"] in ("proposed", "approved"):
            conn.execute("UPDATE plans SET status = 'superseded' WHERE plan_id = ?", (prev["plan_id"],))
        plan_id = "plan_" + secrets.token_hex(8)
        conn.execute("INSERT INTO plans (plan_id, case_id, revision, status, plan_json, digest, created_at) "
                     "VALUES (?, ?, ?, 'proposed', ?, ?, ?)",
                     (plan_id, case_id, revision, json.dumps(plan), digest, now.isoformat(timespec="seconds")))
        conn.execute("UPDATE cases SET state = ?, updated_at = ? WHERE case_id = ?",
                     (CaseState.NEEDS_REVIEW.value, now.isoformat(timespec="seconds"), case_id))
        audit.append_event(conn, case_id, session.user.user_id, "PLAN_PROPOSED" if revision == 1 else "PLAN_EDITED",
                           {"plan_id": plan_id, "revision": revision, "digest": digest,
                            "selected_quote": req.selected_quote_label,
                            "superseded_plan": prev["plan_id"] if prev else None}, now)
    return case_view(conn, svc, session, case_id)


def approve_plan(conn, svc: Services, session: Session, case_id: str, req: PlanDecisionRequest,
                 idem_key: str | None) -> tuple[dict, bool]:
    """Returns (response, replayed). Refused attempts go to the access log."""
    try:
        return _approve_plan(conn, svc, session, case_id, req, idem_key)
    except WorkflowError as exc:
        audit.log_access(conn, svc.now(), session.user.user_id, "approve_plan", case_id,
                         f"refused {exc.status}: {exc.detail}"[:160])
        raise


def _approve_plan(conn, svc: Services, session: Session, case_id: str, req: PlanDecisionRequest,
                  idem_key: str | None) -> tuple[dict, bool]:
    if not idem_key or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", idem_key):
        raise WorkflowError(400, "Idempotency-Key header (8-80 characters) is required")
    _require_student(session)
    request_digest = _digest({"case_id": case_id, "revision": req.plan_revision, "digest": req.plan_digest})
    now = svc.now()
    with tx(conn):
        prior = conn.execute("SELECT * FROM idempotency WHERE user_id = ? AND idem_key = ?",
                             (session.user.user_id, idem_key)).fetchone()
        if prior:
            if prior["request_digest"] != request_digest:
                raise WorkflowError(409, "Idempotency-Key was already used for a different request")
            return json.loads(prior["response_json"]), True
        row = _load_case(conn, session, case_id, write=True)
        analysis = json.loads(row["analysis_json"] or "null")
        if row["state"] == CaseState.BLOCKED.value or not analysis or \
                analysis["policy"]["decision"] != Decision.PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION.value:
            raise WorkflowError(409, "payment hold: approval is not possible for this case")
        if row["state"] == CaseState.APPROVED.value:
            raise WorkflowError(409, "plan is already approved. Edit the plan to create a new revision.")
        plan = _current_plan(conn, case_id)
        if plan is None or plan["status"] != "proposed" or plan["revision"] != req.plan_revision \
                or plan["digest"] != req.plan_digest:
            raise WorkflowError(409, "plan revision or digest is stale. Reload the case and review the plan again.")
        conn.execute("UPDATE plans SET status = 'approved' WHERE plan_id = ?", (plan["plan_id"],))
        conn.execute("UPDATE cases SET state = ?, updated_at = ? WHERE case_id = ?",
                     (CaseState.APPROVED.value, now.isoformat(timespec="seconds"), case_id))
        event_id = audit.append_event(conn, case_id, session.user.user_id, "PLAN_APPROVED", {
            "plan_id": plan["plan_id"], "revision": plan["revision"], "digest": plan["digest"],
            "idempotency_key_sha256": hashlib.sha256(idem_key.encode()).hexdigest()}, now)
        response = {"case_id": case_id, "state": CaseState.APPROVED.value, "plan_id": plan["plan_id"],
                    "plan_revision": plan["revision"], "plan_status": "approved", "audit_event_id": event_id,
                    "execution": "NOT_EXECUTED. Sandbox plan only. No money moved."}
        conn.execute("INSERT INTO idempotency (user_id, idem_key, case_id, request_digest, response_json, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (session.user.user_id, idem_key, case_id, request_digest,
                                                   json.dumps(response), now.isoformat(timespec="seconds")))
    return response, False


def deny_plan(conn, svc: Services, session: Session, case_id: str, req: PlanDecisionRequest) -> dict:
    _require_student(session)
    now = svc.now()
    with tx(conn):
        row = _load_case(conn, session, case_id, write=True)
        plan = _current_plan(conn, case_id)
        if plan is None or plan["status"] != "proposed" or plan["revision"] != req.plan_revision \
                or plan["digest"] != req.plan_digest:
            raise WorkflowError(409, "no matching proposed plan to deny")
        if row["state"] != CaseState.NEEDS_REVIEW.value:
            raise WorkflowError(409, f"cannot deny a plan in state {row['state']}")
        conn.execute("UPDATE plans SET status = 'denied' WHERE plan_id = ?", (plan["plan_id"],))
        # Denial keeps the case state, the analysis and the quotes unchanged.
        audit.append_event(conn, case_id, session.user.user_id, "PLAN_DENIED",
                           {"plan_id": plan["plan_id"], "revision": plan["revision"],
                            "reason": (req.reason or "")[:300]}, now)
    return case_view(conn, svc, session, case_id)


# ---------------------------------------------------------------- uploads


def add_upload(conn, svc: Services, session: Session, case_id: str, slip_id: str | None, filename: str | None,
               data: bytes) -> dict:
    _require_student(session)
    row = _load_case(conn, session, case_id, write=True)
    if row["state"] != CaseState.DRAFT.value:
        raise WorkflowError(409, "add receipts before the analysis")
    if slip_id is not None and not re.fullmatch(r"[A-Za-z0-9-]{3,40}", slip_id):
        raise WorkflowError(422, "invalid slip_id")
    from .uploads import UploadRejected
    try:
        meta = inspect_upload(filename, data, svc.settings.max_upload_bytes)
    except UploadRejected as exc:
        now = svc.now()
        with tx(conn):
            audit.log_access(conn, now, session.user.user_id, "upload", case_id, f"rejected: {exc}"[:120])
        raise WorkflowError(422, str(exc)) from None
    now = svc.now()
    upload_id = "upl_" + secrets.token_hex(8)
    with tx(conn):
        conn.execute("INSERT INTO uploads (upload_id, case_id, owner_id, slip_id, safe_name, media_type, size, sha256, "
                     "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (upload_id, case_id, session.user.user_id, slip_id, meta.safe_name, meta.media_type, meta.size,
                      meta.sha256, now.isoformat(timespec="seconds")))
        audit.append_event(conn, case_id, session.user.user_id, "UPLOAD_RECEIVED",
                           {"upload_id": upload_id, "slip_id": slip_id, "sha256": meta.sha256, "size": meta.size,
                            "media_type": meta.media_type, "content_stored": False}, now)
    return {"upload_id": upload_id, "safe_name": meta.safe_name, "media_type": meta.media_type, "size": meta.size,
            "sha256": meta.sha256, "content_stored": False,
            "note": "Metadata only. The receipt is not proof of settlement."}


# ---------------------------------------------------------------- views


def case_view(conn, svc: Services, session: Session, case_id: str) -> dict:
    row = _load_case(conn, session, case_id, write=False)
    plans = conn.execute("SELECT * FROM plans WHERE case_id = ? ORDER BY revision", (case_id,)).fetchall()
    events = audit.list_events(conn, case_id)
    stored = json.loads(row["input_json"])
    stored.pop("sanitized_text", None)  # raw text is never returned after creation
    stored.pop("offer_text", None)
    return {
        "case_id": row["case_id"],
        "case_type": row["case_type"],
        "state": row["state"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "input": stored,
        "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else None,
        "quotes": json.loads(row["quotes_json"]) if row["quotes_json"] else None,
        "plans": [{"plan_id": p["plan_id"], "revision": p["revision"], "status": p["status"], "digest": p["digest"],
                   "plan": json.loads(p["plan_json"]), "created_at": p["created_at"]} for p in plans],
        "audit_events": [{"event_id": e["event_id"], "seq": e["seq"], "event_type": e["event_type"], "at": e["at"],
                          "actor_id": e["actor_id"]} for e in events],
        "audit_chain_valid": audit.verify_chain(events),
        "sandbox_notice": SANDBOX_NOTICE,
        "viewer_role": session.user.role,
    }


def list_cases(conn, session: Session) -> list[dict]:
    u = session.user
    if u.role == "student":
        rows = conn.execute("SELECT case_id, case_type, state, created_at FROM cases WHERE owner_id = ? "
                            "ORDER BY created_at DESC", (u.user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT case_id, case_type, state, created_at FROM cases WHERE escalated = 1 AND "
                            "institution_id = ? ORDER BY created_at DESC", (u.institution_id,)).fetchall()
    return [dict(r) for r in rows]


def office_escalations(conn, session: Session) -> dict:
    if session.user.role != "office_reviewer":
        raise WorkflowError(403, "office reviewers only")
    rows = conn.execute("SELECT case_id, case_type, state, created_at, analysis_json, intermediary_hash FROM cases "
                        "WHERE escalated = 1 AND institution_id = ? ORDER BY created_at",
                        (session.user.institution_id,)).fetchall()
    counts: dict[str, int] = {}
    for r in rows:
        if r["intermediary_hash"]:
            counts[r["intermediary_hash"]] = counts.get(r["intermediary_hash"], 0) + 1
    items = []
    for r in rows:
        a = json.loads(r["analysis_json"] or "{}")
        pol = a.get("policy") or {}
        h = r["intermediary_hash"]
        items.append({"case_id": r["case_id"], "case_type": r["case_type"], "state": r["state"],
                      "created_at": r["created_at"], "overall_status": pol.get("overall_status"),
                      "reasons": pol.get("reasons", [])[:10],
                      "intermediary_ref": h[:12] if h else None,
                      "cases_with_same_intermediary": counts.get(h, 0) if h else 0})
    return {"institution_id": session.user.institution_id, "escalations": items,
            "note": "Read-only. Student identities and raw messages are not shown. Intermediary contacts are hashed."}
