"""Safe-to-contact checklist and a draft verification e-mail.

The draft goes only to the contact in the curated registry, never to an
address or phone number from the pasted message. CEKBAO never sends it.
"""
from __future__ import annotations

from .models import CheckStatus, Decision, PolicyResult
from .registry import InstitutionEntry

IC3_URL = "https://www.ic3.gov/"

SIGNAL_LABELS = {
    "DEADLINE_PRESSURE": "short deadline",
    "DISCOUNT_OFFER": "discount offer",
    "EASY_PAYMENT_OFFER": "offer to handle the payment for me",
    "BANK_AGENT_IMPERSONATION": "sender claims to be a bank agent",
    "THREAT_OR_AUTHORITY_PRESSURE": "threat about visa, arrest or legal action",
    "AUTHORITY_CLAIM": "mentions a government authority",
    "SECRET_REQUEST": "asks for a password, OTP or PIN",
    "OFF_CHANNEL_CONTACT": "asks me to use a chat app or phone number",
    "PROMPT_INJECTION": "the message contains hidden instructions aimed at software",
    "HIDDEN_CHARACTERS": "the message contains hidden characters",
    "UNGROUNDED_MODEL_OUTPUT": "an automated reading could not be confirmed",
    "DUPLICATE_INTERMEDIARY_REQUEST": "the same contact sent more than one payment request",
}


def build_escalation(entry: InstitutionEntry | None, result: PolicyResult, case_id: str,
                     received_on: str, kind: str = "payment request") -> dict:
    hold = result.decision is Decision.HOLD_DO_NOT_PAY
    issues = [f for f in result.findings if f.status is not CheckStatus.MATCHED_SOURCE and f.required]
    lines = []
    for f in issues:
        observed = f.observed if f.observed is not None else "(missing)"
        lines.append(f"- {f.label}: {observed}. {f.explanation}")
    for s in result.risk_signals:
        label = SIGNAL_LABELS.get(s.signal_id, s.signal_id)
        if s.signal_id == "PROMPT_INJECTION":
            # Do not forward attacker instructions into an e-mail to the institution.
            lines.append(f"- Warning sign: {label}.")
        else:
            lines.append(f"- Warning sign: {label} (\"{s.evidence}\").")

    checklist = [
        "Do not reply to the sender. Do not use links, phone numbers or chat contacts from the message.",
        "Open the institution website by typing the address from your admission documents.",
        "Never share passwords, OTP codes, PINs or passport scans with anyone who requests payment.",
        "Pay only through the channel your official portal or finance office confirms in writing.",
        "If you already sent money, call your bank fraud line now (use the number on your card or the "
        "official bank app) and ask for a recall.",
    ]
    if entry is not None:
        checklist.insert(1, f"Contact {entry.official_contact.office}: {entry.official_contact.email}"
                            + (f", {entry.official_contact.phone}" if entry.official_contact.phone else "")
                            + f". Registry source: {entry.official_contact.contact_page_url}")
        if entry.country == "US":
            checklist.append(f"In the US you can also report fraud to the FBI IC3: {IC3_URL}")
    else:
        checklist.insert(1, "The institution is not in the registry. Find its official finance contact yourself "
                            "from the admission letter or the official website. CEKBAO does not suggest one.")

    draft = None
    if entry is not None:
        body = "\n".join([
            f"Dear {entry.official_contact.office},",
            "",
            f"I received a {kind} on {received_on} that asks me to pay tuition or fees.",
            "Before I take any action, please confirm whether this request comes from your office and which "
            "payment channel I must use.",
            "",
            "Items that do not match your published procedure:" if lines else
            "The request appears to match your published procedure. Please confirm the amount on my invoice.",
            *lines,
            "",
            "I have not paid through the channel in this request. I will wait for your written confirmation.",
            "I can share the original message through your official channel if you request it.",
            "",
            f"Reference: CEKBAO sandbox case {case_id}",
            "",
            "Kind regards,",
            "[Your name and student reference, added by you]",
        ])
        draft = {
            "to": entry.official_contact.email,
            "to_source_url": entry.official_contact.contact_page_url,
            "to_is_synthetic": entry.synthetic,
            "subject": f"Verification request: {kind} received on {received_on}",
            "body": body,
            "auto_send": False,
            "note": "DRAFT ONLY. CEKBAO does not send e-mail. Review it and send it yourself.",
        }
    return {"payment_hold": hold, "checklist": checklist, "draft_email": draft}
