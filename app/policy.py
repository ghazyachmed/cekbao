"""Deterministic policy engine. It owns every status and the payment decision.

Rule summary:
1. Compare each extracted field with the curated registry entry.
2. Any CONFLICT makes the overall status CONFLICT.
3. Otherwise any required NOT_VERIFIABLE makes the overall status NOT_VERIFIABLE.
4. Otherwise the overall status is MATCHED_SOURCE.
5. The decision allows a sandbox payment plan only when the overall status is
   MATCHED_SOURCE and no high-severity risk signal exists. Everything else is
   HOLD_DO_NOT_PAY.
"""
from __future__ import annotations

import re

from .extractor import find_affirmative
from .models import (CheckStatus, Decision, ExtractedRequest, Finding, PaymentMethod, PolicyResult, RiskSignal,
                     Severity)
from .registry import InstitutionEntry
from .sanitize import mask_account
from .urlguard import assess_link, host_matches_domain

FBI_ALERT_URL = ("https://www.fbi.gov/investigate/cyber/alerts/2025/"
                 "impersonation-scheme-targeting-middle-eastern-students-in-the-united-states")
FLYWIRE_SCAM_URL = "https://pay.flywire.com/resources/how-international-students-can-avoid-tuition-payment-scams"
UMTS_CASE_URL = ("https://www.kompas.com/jawa-barat/read/2025/02/24/150000488/"
                 "awal-mula-terbongkar-modus-penipuan-bayar-ukt-tanpa-ribet-273")
SPF_ADVISORY_URL = ("https://www.police.gov.sg/Media-Hub/News/2026/03/"
                    "20260319_police_advisory_on_resurgence_of_impersonation_scams_involving_educational_institutions")

_SIGNALS: list[tuple[str, Severity, str, str, str | None, str | None]] = [
    # (signal_id, severity, regex, explanation, context source, registry statement that conflicts)
    ("DISCOUNT_OFFER", Severity.HIGH,
     r"\b(discounts?|diskon|potongan|cashback|save \d{1,2} ?%|lebih murah|hemat \d{1,2} ?%)",
     "The message offers a discount or saving for paying through this route.", FLYWIRE_SCAM_URL,
     "NO_THIRD_PARTY_DISCOUNT"),
    ("EASY_PAYMENT_OFFER", Severity.HIGH,
     r"\b(tanpa ribet|lebih mudah|easier payment|hassle[- ]free|jasa bayar|bantu bayar|we will pay on your behalf)\b",
     "The message offers to handle tuition payment for you.", UMTS_CASE_URL, "NO_THIRD_PARTY_DISCOUNT"),
    ("BANK_AGENT_IMPERSONATION", Severity.HIGH,
     r"\b(bank (?:representative|officer|agent)|perwakilan (?:dari )?bank|petugas bank|agen bank|pihak bank"
     r"|on behalf of (?:the )?bank|mewakili bank)\b",
     "The sender claims to represent a bank and collects tuition outside the institution channel.",
     UMTS_CASE_URL, "NO_AGENTS"),
    ("THREAT_OR_AUTHORITY_PRESSURE", Severity.HIGH,
     r"\b(visa|status|sevis)\b[^.\n]{0,40}\b(cancel\w*|revok\w*|terminat\w*|dicabut|dibatalkan)\b"
     r"|\b(deport\w*|arrest\w*|ditangkap|legal action|tindakan hukum)\b",
     "The message threatens immigration or legal consequences to force payment.", FBI_ALERT_URL, "NO_THREATS"),
    ("AUTHORITY_CLAIM", Severity.WARNING,
     r"\b(immigration|uscis|homeland security|embassy|consulate|kedutaan|imigrasi|police|polisi)\b",
     "The message invokes a government authority. Authorities do not collect tuition.", FBI_ALERT_URL, None),
    ("SECRET_REQUEST", Severity.HIGH,
     r"\b(send|share|give|provide|reply with|tell us|kirim\w*|berikan|bagikan|sebutkan)\b[^.\n]{0,40}"
     r"\b(otp|one[- ]time (?:password|code)|password|kata sandi|pin|kode verifikasi|cvv)\b",
     "The message asks for a password, OTP, PIN or card security code.", None, None),
    ("OFF_CHANNEL_CONTACT", Severity.WARNING,
     r"\b(whatsapp|telegram|line id|wechat|wa\.me|chat (?:me|us) on)\b",
     "The message moves the conversation to a chat app. Use only the registry contact.", SPF_ADVISORY_URL, None),
]
_SIGNAL_RE = [(sid, sev, re.compile(rx, re.IGNORECASE), expl, src, stmt) for sid, sev, rx, expl, src, stmt in _SIGNALS]

_ACCOUNT_METHODS = {PaymentMethod.INTERNATIONAL_WIRE, PaymentMethod.VIRTUAL_ACCOUNT, PaymentMethod.DOMESTIC_TRANSFER}


def _norm_name(s: str) -> str:
    s = re.sub(r"\(synthetic\)", "", s, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", s.casefold())).strip()


def detect_risk_signals(text: str, sanitize_flags: list[str], injection_hits: list[str],
                        ungrounded: list[str], phones: list[str], deadline_text: str | None = None) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    if deadline_text:
        signals.append(RiskSignal(
            signal_id="DEADLINE_PRESSURE", severity=Severity.WARNING, evidence=deadline_text[:80],
            explanation=("The message sets a short deadline. Pressure to pay fast is a common impersonation pattern. "
                         "Check the due date on your official invoice."), source_url=SPF_ADVISORY_URL))
    for sid, sev, rx, expl, src, _ in _SIGNAL_RE:
        m = find_affirmative(rx, text)
        if m:
            signals.append(RiskSignal(signal_id=sid, severity=sev, evidence=m.group(0)[:80], explanation=expl,
                                      source_url=src))
    if phones and not any(s.signal_id == "OFF_CHANNEL_CONTACT" for s in signals):
        signals.append(RiskSignal(signal_id="OFF_CHANNEL_CONTACT", severity=Severity.WARNING,
                                  evidence=f"{len(phones)} phone number(s) in message",
                                  explanation="Do not call numbers from the message. Use only the registry contact.",
                                  source_url=SPF_ADVISORY_URL))
    if injection_hits:
        signals.append(RiskSignal(
            signal_id="PROMPT_INJECTION", severity=Severity.HIGH, evidence="; ".join(injection_hits)[:160],
            explanation=("The message contains text that tries to instruct the system. CEKBAO treats it as data "
                         "and holds the payment."), source_url=None))
    if "HIDDEN_CHARACTERS_REMOVED" in sanitize_flags:
        signals.append(RiskSignal(signal_id="HIDDEN_CHARACTERS", severity=Severity.WARNING,
                                  evidence="zero-width or bidirectional control characters",
                                  explanation="Hidden characters can disguise links or names. CEKBAO removed them.",
                                  source_url=None))
    if ungrounded:
        signals.append(RiskSignal(signal_id="UNGROUNDED_MODEL_OUTPUT", severity=Severity.WARNING,
                                  evidence=", ".join(ungrounded),
                                  explanation="Model values not found in the message were discarded.",
                                  source_url=None))
    return signals


def evaluate_request(ex: ExtractedRequest, entry: InstitutionEntry | None, text: str,
                     sanitize_flags: list[str], injection_hits: list[str],
                     ungrounded: list[str] | None = None) -> PolicyResult:
    ungrounded = ungrounded or []
    findings: list[Finding] = []
    src = entry.source.url if entry else None
    syn = entry.synthetic if entry else True
    domains = list(entry.official_domains) if entry else []

    def add(check_id, label, status, required, observed, expected, explanation, source=src):
        findings.append(Finding(check_id=check_id, label=label, status=status, required=required,
                                observed=observed, expected=expected, explanation=explanation,
                                source_url=source, source_synthetic=syn))

    # 1. Institution
    if entry is None:
        add("INSTITUTION", "Institution in registry", CheckStatus.NOT_VERIFIABLE, True, ex.claimed_institution, None,
            "The claimed institution is not in the curated registry. CEKBAO does not guess. "
            "Find the official contact from your admission documents.", None)
    else:
        add("INSTITUTION", "Institution in registry", CheckStatus.MATCHED_SOURCE, True, ex.claimed_institution,
            entry.display_name, "The claimed institution matches a curated registry entry.")

    # 2. Sender domain
    if not ex.sender_domain:
        add("SENDER_DOMAIN", "Sender e-mail domain", CheckStatus.NOT_VERIFIABLE, True, None, ", ".join(domains) or None,
            "No sender e-mail address found. Chat or SMS messages cannot be matched to an official domain.")
    elif entry is None:
        add("SENDER_DOMAIN", "Sender e-mail domain", CheckStatus.NOT_VERIFIABLE, True, ex.sender_domain, None,
            "No reviewed domain exists for comparison.", None)
    elif any(host_matches_domain(ex.sender_domain, d) for d in domains):
        add("SENDER_DOMAIN", "Sender e-mail domain", CheckStatus.MATCHED_SOURCE, True, ex.sender_domain,
            ", ".join(domains),
            "The From domain matches the registry. A From header can be forged, so open the portal yourself.")
    else:
        core = [d.split(".")[0] for d in domains]
        lookalike = any(c in ex.sender_domain for c in core)
        add("SENDER_DOMAIN", "Sender e-mail domain", CheckStatus.CONFLICT, True, ex.sender_domain, ", ".join(domains),
            "Look-alike sender domain." if lookalike else "The sender domain is not an official domain.")

    # 3. Links
    for url in ex.urls[:5]:
        a = assess_link(url, domains)
        add("LINK_DOMAIN", "Link host", a.status, True, url[:200], ", ".join(domains) or None, a.reason)

    # 4. Beneficiary name
    names = [c.beneficiary_name for c in (entry.approved_channels if entry else []) if c.beneficiary_name]
    if not ex.beneficiary_name:
        add("BENEFICIARY_NAME", "Payee name", CheckStatus.NOT_VERIFIABLE, True, None, ", ".join(names) or None,
            "The payee is missing. Ask the official office for the payee. CEKBAO does not guess.")
    elif entry is None:
        add("BENEFICIARY_NAME", "Payee name", CheckStatus.NOT_VERIFIABLE, True, ex.beneficiary_name, None,
            "No approved payee exists for comparison.", None)
    elif _norm_name(ex.beneficiary_name) in {_norm_name(n) for n in names}:
        add("BENEFICIARY_NAME", "Payee name", CheckStatus.MATCHED_SOURCE, True, ex.beneficiary_name, ", ".join(names),
            "The payee name matches an approved channel. This is not bank-level payee authentication.")
    else:
        add("BENEFICIARY_NAME", "Payee name", CheckStatus.CONFLICT, True, ex.beneficiary_name, ", ".join(names),
            "The payee name differs from every approved channel.")

    # 5. Account
    channels = list(entry.approved_channels) if entry else []
    needs_account = any(m in _ACCOUNT_METHODS for m in ex.payment_methods)
    if ex.beneficiary_account:
        masked = mask_account(ex.beneficiary_account)
        if entry is None:
            add("BENEFICIARY_ACCOUNT", "Payee account", CheckStatus.NOT_VERIFIABLE, True, masked, None,
                "No approved account exists for comparison.", None)
        elif any(c.account_matches(ex.beneficiary_account) for c in channels):
            add("BENEFICIARY_ACCOUNT", "Payee account", CheckStatus.MATCHED_SOURCE, True, masked,
                "approved channel account (masked)",
                "The account matches an approved channel in the registry.")
        else:
            add("BENEFICIARY_ACCOUNT", "Payee account", CheckStatus.CONFLICT, True, masked,
                "approved channel account (masked)", "The account is not an approved institution account.")
    elif needs_account:
        add("BENEFICIARY_ACCOUNT", "Payee account", CheckStatus.NOT_VERIFIABLE, True, None, None,
            "The message requests a transfer but gives no account. Do not accept an account by phone or chat.")

    # 6. SWIFT / bank country
    if ex.swift_bic:
        swifts = [c.swift_bic for c in channels if c.swift_bic]
        country = ex.swift_bic[4:6]
        if entry is None:
            add("SWIFT_BIC", "Bank SWIFT/BIC", CheckStatus.NOT_VERIFIABLE, True, ex.swift_bic, None,
                "No approved SWIFT/BIC exists for comparison.", None)
        elif ex.swift_bic in swifts:
            add("SWIFT_BIC", "Bank SWIFT/BIC", CheckStatus.MATCHED_SOURCE, True, ex.swift_bic, ", ".join(swifts),
                "The SWIFT/BIC matches the approved wire channel.")
        else:
            add("SWIFT_BIC", "Bank SWIFT/BIC", CheckStatus.CONFLICT, True, ex.swift_bic, ", ".join(swifts) or None,
                f"The SWIFT/BIC is not approved. Its country code is {country}; the institution country is "
                f"{entry.country}." if country != entry.country else "The SWIFT/BIC is not approved.")

    # 7. Payment method
    approved_methods = {c.method for c in channels}
    observed = ", ".join(m.value for m in ex.payment_methods) or None
    if not ex.payment_methods:
        add("PAYMENT_METHOD", "Payment method", CheckStatus.NOT_VERIFIABLE, True, None,
            ", ".join(sorted(approved_methods)) or None, "No payment method was identified in the message.")
    elif entry is None:
        add("PAYMENT_METHOD", "Payment method", CheckStatus.NOT_VERIFIABLE, True, observed, None,
            "No approved method list exists for comparison.", None)
    else:
        bad = [m.value for m in ex.payment_methods if m.value not in approved_methods]
        if bad:
            stmt = entry.statement("NO_PERSONAL_ACCOUNTS")
            add("PAYMENT_METHOD", "Payment method", CheckStatus.CONFLICT, True, observed,
                ", ".join(sorted(approved_methods)),
                f"Not an approved method: {', '.join(bad)}." + (f" Registry: {stmt.text}" if stmt else ""))
        else:
            add("PAYMENT_METHOD", "Payment method", CheckStatus.MATCHED_SOURCE, True, observed,
                ", ".join(sorted(approved_methods)), "The method is on the approved channel list.")

    # 8. Amount (informational, CEKBAO cannot see the invoice)
    if ex.amount:
        stmt = entry.statement("INVOICE_IN_PORTAL") if entry else None
        add("AMOUNT", "Requested amount", CheckStatus.NOT_VERIFIABLE, False, f"{ex.currency or ''} {ex.amount}".strip(),
            stmt.text if stmt else None,
            "CEKBAO cannot see your invoice. Compare this amount with the invoice in the official portal.")

    # Risk signals and registry policy conflicts
    signals = detect_risk_signals(text, sanitize_flags, injection_hits, ungrounded, ex.contact_phones,
                                  ex.deadline_text)
    if entry is not None:
        seen: set[str] = set()
        for sid, _, _, _, _, stmt_id in _SIGNAL_RE:
            if not stmt_id or stmt_id in seen or not any(s.signal_id == sid for s in signals):
                continue
            stmt = entry.statement(stmt_id)
            if stmt:
                seen.add(stmt_id)
                sig = next(s for s in signals if s.signal_id == sid)
                add(f"POLICY_{stmt_id}", "Documented procedure", CheckStatus.CONFLICT, True, sig.evidence, stmt.text,
                    "The message contradicts the documented payment procedure.")

    conflicts = [f for f in findings if f.status is CheckStatus.CONFLICT]
    unverifiable = [f for f in findings if f.required and f.status is CheckStatus.NOT_VERIFIABLE]
    if conflicts:
        overall = CheckStatus.CONFLICT
    elif unverifiable:
        overall = CheckStatus.NOT_VERIFIABLE
    else:
        overall = CheckStatus.MATCHED_SOURCE
    high = [s for s in signals if s.severity is Severity.HIGH]
    reasons: list[str] = [f"{f.check_id}: {f.status.value}" for f in conflicts + unverifiable]
    reasons += [f"RISK {s.signal_id}" for s in high]
    if overall is CheckStatus.MATCHED_SOURCE and not high:
        decision = Decision.PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION
        reasons.append("All required fields match the registry. A sandbox plan needs explicit student approval.")
    else:
        decision = Decision.HOLD_DO_NOT_PAY
    return PolicyResult(overall_status=overall, decision=decision, findings=findings, risk_signals=signals,
                        reasons=reasons)
