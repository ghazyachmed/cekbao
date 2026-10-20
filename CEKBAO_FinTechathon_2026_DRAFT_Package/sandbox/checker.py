"""CEKBAO deterministic offline demonstration only. NOT a deployed AI agent."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import json

TRUSTED_POLICIES = {
    "DEMO-INTL": {
        "official_domain": "university.example.edu",
        "payee": "Example University Official Tuition Account",
        "permitted_channel": "official_portal",
        "source": "sandbox://policies/DEMO-INTL",
    },
    "DEMO-ID": {
        "official_domain": "campus.example.ac.id",
        "payee": "Example Campus Billing Account",
        "permitted_channel": "bank_va",
        "source": "sandbox://policies/DEMO-ID",
    },
}


def domain_from_url(url: str) -> str:
    """Parse a domain for an offline comparison; never fetch remote URLs."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return ""
        return parsed.hostname.lower().rstrip('.')
    except ValueError:
        return ""


def analyze(item: dict) -> dict:
    """Verify against SYNTHETIC reference policies, without verifying money movement."""
    case_id = str(item.get("id", "unknown"))
    inst = str(item.get("institution", ""))
    policy = TRUSTED_POLICIES.get(inst)
    base = {"id": case_id, "synthetic": True, "verified_bank_settlement": False,
            "source": policy["source"] if policy else None,
            "risk_flags": [], "status": "NOT_VERIFIABLE", "next_action": "Contact the university using its independently obtained official website."}
    if not policy:
        base["risk_flags"].append("UNKNOWN_INSTITUTION")
        return base
    domain = domain_from_url(str(item.get("request_url", "")))
    if not domain or domain != policy["official_domain"]:
        base["risk_flags"].append("REQUEST_DOMAIN_MISMATCH")
    if str(item.get("payee", "")) != policy["payee"]:
        base["risk_flags"].append("PAYEE_MISMATCH")
    if str(item.get("channel", "")) != policy["permitted_channel"]:
        base["risk_flags"].append("PAYMENT_CHANNEL_MISMATCH")
    if item.get("urgent_pressure") is True:
        base["risk_flags"].append("URGENCY_PRESSURE")
    if item.get("slip_id"):
        ledger = item.get("synthetic_university_ledger", {})
        if not isinstance(ledger, dict) or item["slip_id"] not in ledger:
            base["risk_flags"].append("SLIP_NOT_FOUND_IN_SYNTHETIC_LEDGER")
        else:
            try:
                slip_amount = Decimal(str(item.get("amount", "")))
                ledger_amount = Decimal(str(ledger[item["slip_id"]]))
                if slip_amount <= 0 or slip_amount != ledger_amount:
                    base["risk_flags"].append("LEDGER_AMOUNT_MISMATCH")
            except (InvalidOperation, TypeError):
                base["risk_flags"].append("INVALID_AMOUNT")
    if base["risk_flags"]:
        base["status"] = "REQUIRES_OFFICIAL_CHECK"
    else:
        base["status"] = "MATCHES_SYNTHETIC_POLICY_ONLY"
        base["next_action"] = "Open the university portal independently. This sandbox match does not establish settlement."
    return base


def load_fixture_file(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
