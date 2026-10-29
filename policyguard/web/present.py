"""Case view model for templates. Every value comes from the stored case, decisions and evidence snapshot."""
from __future__ import annotations

from policyguard.domain import normalize

from . import display
from .i18n import t, tn

LANGUAGE_NAMES = {"en": "English", "fr": "French", "de": "German", "es": "Spanish", "id": "Indonesian",
                  "zh": "Chinese", "ja": "Japanese"}
FIELD_ORDER = ("payee_name", "account_number", "bank_name", "swift_bic", "amount", "currency", "channel",
               "due_date", "institution_name")
ACCOUNT_FIELDS = {"account_number", "swift_bic", "amount"}


def _effective(v: dict) -> str:
    tz = v.get("valid_tz")
    if not v.get("valid_from"):
        return t("evidence.effective_unknown")
    start = display.date_label(v["valid_from"], tz)
    if v.get("valid_to"):
        return t("evidence.effective_until", **{"from": start, "to": display.date_label(v["valid_to"], tz)})
    return t("evidence.effective_open", **{"from": start})


def _card(v: dict, role: str) -> dict:
    c = v["citation"]
    lang = c.get("language", "en")
    return {"role": role, "title": c["source_title"], "issuer": v["issuer_id"],
            "level": display.evidence_level(v["evidence_level"]), "quote": c["quote"], "locator": c["locator"],
            "language": lang, "language_name": LANGUAGE_NAMES.get(lang, lang), "translation": c.get("translation"),
            "effective": _effective(v), "retrieved": t("evidence.retrieved",
                                                       date=display.date_label(v.get("fetched_at"), v.get("valid_tz"))),
            "url": v["source_url"], "synthetic": v.get("synthetic", True), "version_label": v["version_label"],
            "version_id": v["version_id"], "source_hash": v["source_hash"], "valid_tz": v.get("valid_tz"),
            "revoked": bool(v.get("revoked_at"))}


COMPARE_FIELDS = (("payee_name", "payee_name"), ("account_number", "account_number"), ("swift_bic", "swift_bic"),
                  ("currency", "currency"), ("channel", "channels"))
FIELD_REASONS = {"ACCOUNT_MISMATCH", "PAYEE_MISMATCH", "CURRENCY_MISMATCH", "SWIFT_MISMATCH", "CHANNEL_NOT_ALLOWED",
                 "ALL_FIELDS_MATCH"}
VERDICT_TONE = {"agrees": "ok", "conflicts": "bad", "not_stated": "warn", "not_in_policy": "neutral",
                "sources_disagree": "review", "unverified": "warn", "unverified_differs": "bad", "no_policy": "neutral"}
VERDICT_ICON = {"ok": "check", "bad": "stop", "warn": "question", "review": "person", "neutral": "info"}


def _same(field: str, a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    if field == "account_number":
        return normalize.account(a) == normalize.account(b)
    if field == "payee_name":
        return normalize.name(a) == normalize.name(b)
    if field == "channel":
        return a in (b or "").split(",")
    return normalize.code(a) == normalize.code(b)


def _comparison(a: dict, claim: dict, versions: dict) -> dict:
    """Instruction vs policy per detail. Verdicts follow the rule findings, so table and decision agree."""
    reasons = {f["reason"] for f in a["findings"]}
    mismatched = {f["field"] for f in a["findings"] if f["reason"] in FIELD_REASONS - {"ALL_FIELDS_MATCH"}}
    if "SOURCE_CONFLICT" in reasons:
        mode, ids = "sources", a["applied_version_ids"]
    elif "ISSUER_NOT_AUTHORIZED" in reasons:
        mode, ids = "unauthorized", a["considered_version_ids"]
    else:
        mode, ids = "policy", a["applied_version_ids"][:1]
    cols = [versions[i] for i in ids if i in versions]
    headers = []
    for n, v in enumerate(cols, 1):
        title = (t("compare.source_n", n=n) if mode == "sources" else t("compare.unauthorized") if mode == "unauthorized"
                 else t("compare.policy_states"))
        headers.append({"header": title, "sub": t("compare.policy_sub", label=v["version_label"], effective=_effective(v))})
    rows, unknown = [], [t("compare.unknown.settlement")]
    for field, key in COMPARE_FIELDS:
        c = claim.get(field)
        instr = c["value"] if c else None
        policy_vals = [",".join(v["payee"].get(key) or []) if key == "channels" else v["payee"].get(key) for v in cols]
        if not cols:
            verdict = "no_policy"
        elif instr is None:
            verdict = "not_stated"
            unknown.append(t("compare.unknown.field", field=t(f"field.{field}").lower()))
        elif mode == "sources" and len({normalize.account(x or "") if field == "account_number" else x for x in policy_vals}) > 1:
            verdict = "sources_disagree"
        elif mode == "unauthorized":
            verdict = "unverified" if _same(field, instr, policy_vals[0]) else "unverified_differs"
        elif field in mismatched:
            verdict = "conflicts"
        elif policy_vals[0] in (None, ""):
            verdict = "not_in_policy"
        else:
            verdict = "agrees"
        tone = VERDICT_TONE[verdict]
        shown = display.channel(instr) if field == "channel" else instr
        rows.append({"field": field, "label": t(f"field.{field}"), "instruction": shown, "numeric": field in ACCOUNT_FIELDS,
                     "policy": [display.channel(x) if field == "channel" else x for x in policy_vals],
                     "verdict": verdict, "verdict_label": t(f"compare.{verdict}"), "tone": tone, "icon": VERDICT_ICON[tone]})
    if "END_DATE_UNKNOWN" in a["limitations"]:
        unknown.append(t("compare.unknown.end_date"))
    if mode == "unauthorized":
        unknown.append(t("compare.unknown.authority"))
    if mode == "sources":
        unknown.append(t("compare.unknown.sources"))
    count = lambda v: sum(r["verdict"] == v for r in rows)  # noqa: E731
    parts = [(count("conflicts"), "compare.n_conflict"), (count("agrees"), "compare.n_agree"),
             (count("not_stated"), "compare.n_missing")]
    summary = ", ".join(tn(key, n) for n, key in parts if n) + "." if any(n for n, _ in parts) else None
    return {"columns": headers, "rows": rows, "unknown": unknown, "summary": summary if mode == "policy" and cols else None}


def _assessment(a: dict, tz: str, institution: str | None, claim: dict | None = None) -> dict:
    versions = {v["version_id"]: v for v in (a.get("evidence_snapshot") or {}).get("versions", [])}
    reasons = [f["reason"] for f in a["findings"]]
    cards = []
    if "SOURCE_CONFLICT" in reasons:
        cards = [_card(versions[i], "conflicting") for i in a["applied_version_ids"] if i in versions]
    elif "ISSUER_NOT_AUTHORIZED" in reasons:
        cards = [_card(versions[i], "unauthorized") for i in a["considered_version_ids"] if i in versions]
    else:
        cards = [_card(versions[i], "applied") for i in a["applied_version_ids"] if i in versions]
        for f in a["findings"]:
            if f["reason"] == "MATCHES_SUPERSEDED_POLICY" and f.get("version_id") in versions:
                cards.append(_card(versions[f["version_id"]], "superseded"))
    target = a.get("target_time")
    kind = a["assessment_kind"]
    when = display.date_label(target, tz) if target else None
    if kind == "HISTORICAL":
        heading = t("result.for_earlier_payment_on", date=when)
    else:
        heading = t("result.for_payment_on", date=when) if when else t("result.no_date")
    order = {"ACCOUNT_MISMATCH": 0, "PAYEE_MISMATCH": 1, "MATCHES_SUPERSEDED_POLICY": 2}
    findings = sorted(a["findings"], key=lambda f: order.get(f["reason"], 5))
    return {"kind": kind, "heading": heading, "decision": display.decision(a["policy_decision"]),
            "next_action": display.next_action(a["next_action"], institution),
            "explanations": [display.reason(f) for f in findings],
            "notes": [display.reason(f) for f in findings if f["reason"] not in FIELD_REASONS],
            "comparison": _comparison(a, claim or {}, versions),
            "evidence_level": display.evidence_level(a.get("evidence_level")), "cards": cards,
            "compare": "SOURCE_CONFLICT" in reasons, "limitations": a["limitations"],
            "needs_reevaluation": a.get("needs_reevaluation", False), "rule_version": a["rule_version"],
            "model_version": a["model_version"], "policy_epoch": a["policy_epoch"],
            "request_hash": a["request_hash"], "transaction_status": a["transaction_status"]}


def present_case(view: dict) -> dict:
    tz = view.get("payment_tz") or "UTC"
    inst = view.get("institution")
    institution = inst["name"] if inst else (view.get("institution_query") or None)
    job = view.get("job") or {}
    state = display.job_state(view["state"], job.get("run_after") if view["state"] == "RETRY_WAIT" else None)
    assessments = sorted(view["assessments"], key=lambda a: a["assessment_kind"] != "NEXT_PAYMENT")
    items = [_assessment(a, tz, institution, view.get("claim") or {}) for a in assessments]
    limitations: list[str] = []
    for a in items:
        for lim in a["limitations"]:
            text = display.limitation(lim)
            if text not in limitations:
                limitations.append(text)
    claim = view.get("claim") or {}
    fields = []
    for name in FIELD_ORDER:
        f = claim.get(name)
        value = display.channel(f["value"]) if f and name == "channel" else (f["value"] if f else None)
        fields.append({"name": name, "label": t(f"field.{name}"), "value": value,
                       "source": t(f"result.source.{f['source']}") if f else None,
                       "quote": f["quote"] if f and f["source"] != "user" else None,
                       "numeric": name in ACCOUNT_FIELDS})
    inference = view.get("inference")
    tokens = None
    if inference and inference.get("prompt_tokens") is not None:
        tokens = t("inference.tokens", prompt=inference["prompt_tokens"], completion=inference["completion_tokens"])
    return {
        "case_id": view["case_id"], "state": state, "done": state["done"], "completed": view["state"] == "COMPLETED",
        "institution": institution, "institution_synthetic": bool(inst and inst.get("synthetic")),
        "contact_url": inst.get("official_contact_url") if inst else None, "tz": tz,
        "created": display.timestamp_label(view["created_at"]), "updated": display.timestamp_label(view["updated_at"]),
        "job": job, "assessments": items, "primary": items[0] if items else None, "limitations": limitations,
        "fields": fields, "inference": display.inference(inference), "inference_mode": (inference or {}).get("mode"),
        "inference_model": (inference or {}).get("model_id"), "tokens": tokens,
        "reviews": [{**r, "when": display.timestamp_label(r["created_at"]),
                     "outcome_label": t(f"review.outcome.{r['outcome']}")} for r in view.get("reviews", [])],
        "row_version": view["row_version"], "instruction_text": view["instruction_text"],
        "needs_reevaluation": any(a["needs_reevaluation"] for a in items), "synthetic": view.get("synthetic", True),
    }
