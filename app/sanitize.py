"""Input sanitation, prompt-injection detection and PII redaction.

Pasted messages are untrusted data. CEKBAO never executes instructions found
inside them. Detection here only produces risk signals. The policy engine
decides the outcome without reading any model opinion.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_HIDDEN = re.compile("[​-‏‪-‮⁠-⁤﻿]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any )?(previous|prior|above|the) (instructions|rules|policy)",
    r"abaikan (semua )?(instruksi|perintah|aturan)",
    r"\bsystem prompt\b",
    r"\byou are now\b",
    r"\bact as (an? )?(admin|administrator|system|developer)",
    r"mark (this|it|the payment|the request)( request| payment)? as (verified|safe|legit(imate)?|approved|matched)",
    r"(set|change|update) (the )?(status|decision|verdict) to",
    r"\b(approve|authorize|authorise) (this|the) (payment|transfer|plan)\b",
    r"(update|overwrite|replace|add to) (the )?(trusted|registry|allowlist|whitelist)",
    r"<\|?(im_start|im_end|system|assistant)\|?>",
    r"(?m)^\s*(system|assistant)\s*:",
    r"\btool_call",
    r"MATCHED_SOURCE",
]
_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


class InputRejected(ValueError):
    """Input fails a hard limit. The API returns HTTP 422."""


@dataclass
class SanitizedText:
    text: str
    flags: list[str] = field(default_factory=list)


def sanitize_text(raw: str, max_chars: int) -> SanitizedText:
    """Normalize Unicode, drop control and hidden characters, enforce length."""
    if not isinstance(raw, str):
        raise InputRejected("message must be text")
    if len(raw) > max_chars:
        raise InputRejected(f"message is longer than {max_chars} characters")
    flags: list[str] = []
    text = unicodedata.normalize("NFKC", raw)
    if _HIDDEN.search(text):
        flags.append("HIDDEN_CHARACTERS_REMOVED")
        text = _HIDDEN.sub("", text)
    if _CONTROL.search(text):
        flags.append("CONTROL_CHARACTERS_REMOVED")
        text = _CONTROL.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise InputRejected("message is empty after sanitation")
    return SanitizedText(text=text, flags=flags)


def detect_injection(text: str) -> list[str]:
    """Return short excerpts of text that tries to instruct the system."""
    hits: list[str] = []
    for rx in _INJECTION_RE:
        m = rx.search(text)
        if m:
            hits.append(" ".join(m.group(0).split())[:80])
    return hits


# PII redaction. Order matters: e-mail first, then IBAN, phone, long digit runs.
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_PHONE = re.compile(
    r"(?<![\w+])(?:\+\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,4}|08\d{2}[\s.-]?\d{3,4}[\s.-]?\d{3,5})(?!\w)")
_LONG_DIGITS = re.compile(r"(?<!\d)(?<!\d[.,])\d{8,24}(?!\d|[.,]\d)")
_LABELED_ID = re.compile(
    r"(?i)\b(passport(?: no\.?| number)?|student id|nim|nik|ktp|no\. paspor)\s*[:#]?\s*([A-Z0-9-]{5,20})")


@dataclass
class Redaction:
    text: str
    mapping: dict[str, str]


def redact(text: str) -> Redaction:
    """Replace e-mail, IBAN, phone, account and ID values with placeholders.

    The mapping stays on the server. Only the redacted text may leave the
    process (for example to a configured LLM endpoint).
    """
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}

    def sub(kind: str):
        def _repl(m: re.Match) -> str:
            value = m.group(0)
            for ph, v in mapping.items():
                if v == value and ph.startswith(f"[{kind}_"):
                    return ph
            counters[kind] = counters.get(kind, 0) + 1
            ph = f"[{kind}_{counters[kind]}]"
            mapping[ph] = value
            return ph
        return _repl

    def sub_labeled(m: re.Match) -> str:
        counters["ID"] = counters.get("ID", 0) + 1
        ph = f"[ID_{counters['ID']}]"
        mapping[ph] = m.group(2)
        return f"{m.group(1)}: {ph}"

    out = _LABELED_ID.sub(sub_labeled, text)
    out = _EMAIL.sub(sub("EMAIL"), out)
    out = _IBAN.sub(sub("ACCOUNT"), out)
    out = _PHONE.sub(sub("PHONE"), out)
    out = _LONG_DIGITS.sub(sub("ACCOUNT"), out)
    return Redaction(text=out, mapping=mapping)


def mask_account(value: str | None) -> str | None:
    if not value:
        return value
    digits = re.sub(r"\s|-", "", value)
    if len(digits) <= 4:
        return "****"
    return "*" * (len(digits) - 4) + digits[-4:]


def mask_phone(value: str | None) -> str | None:
    if not value:
        return value
    digits = re.sub(r"\D", "", value)
    return "***" + digits[-3:] if len(digits) > 3 else "***"
