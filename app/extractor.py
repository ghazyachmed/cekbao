"""Deterministic field extractor (DETERMINISTIC_DEMO mode).

This extractor uses regular expressions on English and Indonesian payment
messages. It is the offline fallback and the baseline for evaluation. It is
not a language model.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .models import ExtractedRequest, PaymentMethod
from .registry import Registry
from .urlguard import extract_urls

_FROM = re.compile(r"(?im)^\s*(?:from|dari)\s*:\s*(.+)$")
_EMAIL = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_INSTITUTION = re.compile(r"(?im)^\s*(?:institution|university|universitas|kampus)\s*:\s*(.+)$")
_BENEFICIARY = re.compile(
    r"(?im)^\s*(?:beneficiary(?: name)?|account name|payee|nama penerima|atas nama|a\.n\.)\s*:\s*(.+)$")
_ACCOUNT = re.compile(
    r"\b(?i:account(?: number| no\.?)?|acct(?: no\.?)?|iban|no\.? ?rekening|nomor rekening|rekening"
    r"|virtual account(?: number)?|nomor va|va)\s*:\s*([A-Z]{2}\d{2}[A-Z0-9]{10,30}|\d(?:[ -]?\d){5,33})(?!\d)")
_BENEFICIARY_INLINE = re.compile(r"(?i)\b(?:a\.n\.|atas nama)\s+([A-Za-z][A-Za-z .'-]{1,80}?)(?=\s*[(\n,]|\.\s|$)")
_SWIFT = re.compile(r"\b(?i:swift|bic)(?:\s*(?i:code))?\s*[:\-]\s*([A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b")
_BANK = re.compile(r"(?im)^\s*(?:bank(?: name)?|nama bank)\s*:\s*(.+)$")
_BANK_COUNTRY = re.compile(r"(?im)^\s*(?:bank country|negara bank)\s*:\s*([A-Za-z ]{2,40})$")
_AMOUNT = re.compile(
    r"(?i)(USD|US\$|IDR|Rp\.?|CNY|RMB|SGD|S\$|EUR|€|\$)\s?(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)")
_AMOUNT_LINE = re.compile(r"(?i)\b(amount|total|pay|payment|deposit|tuition|bayar|sebesar|jumlah|ukt|biaya)\b")
_DEADLINE = re.compile(
    r"(?i)\b(?:within|in)\s+\d{1,2}\s*(?:hours?|hrs?|jam)\b|\bdalam\s+\d{1,2}\s*jam\b|\btoday\b|\bimmediately\b"
    r"|\burgent(?:ly)?\b|\bsegera\b|\bhari ini\b|\bbefore (?:midnight|end of day)\b|\bby (?:tonight|tomorrow)\b"
    r"|\bmalam ini\b|\bbatas waktu\b|\bdeadline\s*:\s*[^\n]{1,40}")
_PHONE = re.compile(
    r"(?<![\w+])(?:\+\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,4}|08\d{2}[\s.-]?\d{3,4}[\s.-]?\d{3,5})(?!\w)")

_NEGATION = re.compile(r"(?i)\b(never|not|don't|do not|no|tidak|jangan|bukan|tanpa melalui)\b")

_METHOD_PATTERNS: list[tuple[PaymentMethod, re.Pattern]] = [
    (PaymentMethod.CRYPTO, re.compile(r"(?i)\b(crypto(?:currency)?|bitcoin|btc|usdt|tether|ethereum|wallet address)\b")),
    (PaymentMethod.GIFT_CARD, re.compile(r"(?i)\bgift ?cards?\b")),
    (PaymentMethod.CASH_OR_AGENT, re.compile(
        r"(?i)\b(?:pay|bayar|transfer|send|kirim|setor)\b[^.\n]{0,40}\b(?:agent|agen|representative|perwakilan|"
        r"courier|kurir|petugas)\b|\b(?:in cash|secara tunai|bayar tunai)\b")),
    (PaymentMethod.E_WALLET, re.compile(r"(?i)\b(e-?wallet|ovo|gopay|shopeepay|alipay|wechat pay|paypal)\b")),
    (PaymentMethod.MONEY_TRANSFER_OPERATOR, re.compile(r"(?i)\b(western union|moneygram)\b")),
    (PaymentMethod.PERSONAL_ACCOUNT, re.compile(
        r"(?i)\b(personal account|private account|my (?:own )?account|rekening pribadi|rekening saya)\b")),
    (PaymentMethod.VIRTUAL_ACCOUNT, re.compile(r"(?i)\bvirtual account\b|\bnomor va\b")),
    (PaymentMethod.INTERNATIONAL_WIRE, re.compile(
        r"(?i)\b(wire transfer|international (?:bank )?transfer|telegraphic transfer|swift)\b")),
    (PaymentMethod.DOMESTIC_TRANSFER, re.compile(
        r"(?i)\b(bank transfer|transfer (?:ke|to) (?:rekening|account|the account)|transfer bank)\b")),
    (PaymentMethod.INSTITUTION_PORTAL, re.compile(r"(?i)\b(student[- ]account portal|payment portal|portal|siakad)\b")),
    (PaymentMethod.CARD, re.compile(r"(?i)\b(credit card|debit card|kartu kredit)\b")),
]

_CCY = {"US$": "USD", "$": "USD", "USD": "USD", "IDR": "IDR", "RP": "IDR", "RP.": "IDR", "CNY": "CNY",
        "RMB": "CNY", "SGD": "SGD", "S$": "SGD", "EUR": "EUR", "€": "EUR"}


def negated(text: str, start: int) -> bool:
    """True when a negation word precedes the match in the same sentence."""
    window = text[max(0, start - 45):start]
    window = re.split(r"[.!?\n]", window)[-1]
    return bool(_NEGATION.search(window))


def find_affirmative(rx: re.Pattern, text: str) -> re.Match | None:
    for m in rx.finditer(text):
        if not negated(text, m.start()):
            return m
    return None


def parse_number(raw: str) -> str | None:
    seps = [i for i, c in enumerate(raw) if c in ".,"]
    if seps:
        last = seps[-1]
        tail = raw[last + 1:]
        if len(tail) == 3:
            raw = re.sub(r"[.,]", "", raw)
        else:
            raw = re.sub(r"[.,]", "", raw[:last]) + "." + tail
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return str(value)


def _amount(text: str) -> tuple[str | None, str | None]:
    candidates = []
    for line in text.splitlines():
        for m in _AMOUNT.finditer(line):
            candidates.append((bool(_AMOUNT_LINE.search(line)), m))
    if not candidates:
        return None, None
    preferred = [m for flag, m in candidates if flag] or [m for _, m in candidates]
    m = preferred[0]
    return parse_number(m.group(2)), _CCY.get(m.group(1).upper(), m.group(1).upper())


def _first(rx: re.Pattern, text: str, group: int = 1) -> str | None:
    m = rx.search(text)
    return m.group(group).strip() if m else None


def detect_methods(text: str) -> list[PaymentMethod]:
    found: list[PaymentMethod] = []
    for method, rx in _METHOD_PATTERNS:
        if find_affirmative(rx, text) and method not in found:
            found.append(method)
    return found


def find_phones(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).strip() for m in _PHONE.finditer(text)))[:5]


def extract_deterministic(text: str, claimed_institution: str | None, registry: Registry) -> ExtractedRequest:
    sender_email = sender_domain = display = None
    from_line = _first(_FROM, text)
    if from_line:
        em = _EMAIL.search(from_line)
        if em:
            sender_email = em.group(0).lower()
            sender_domain = em.group(2).lower().rstrip(".")
        display = from_line.split("<")[0].strip().strip('"') or None
    institution = claimed_institution or _first(_INSTITUTION, text)
    if not institution:
        entry = registry.find_in_text(text)
        institution = entry.display_name if entry else None
    amount, currency = _amount(text)
    swift = _first(_SWIFT, text)
    account = _first(_ACCOUNT, text)
    bank_country = _first(_BANK_COUNTRY, text)
    if not bank_country and swift and len(swift) >= 6:
        bank_country = swift[4:6].upper()
    deadlines = list(dict.fromkeys(m.group(0).strip() for m in _DEADLINE.finditer(text)))[:3]
    return ExtractedRequest(
        sender_email=sender_email,
        sender_domain=sender_domain,
        sender_display_name=display,
        claimed_institution=institution,
        amount=amount,
        currency=currency,
        beneficiary_name=_first(_BENEFICIARY, text) or _first(_BENEFICIARY_INLINE, text),
        beneficiary_account=re.sub(r"[\s-]", "", account) if account else None,
        swift_bic=swift.upper() if swift else None,
        bank_name=_first(_BANK, text),
        bank_country=bank_country,
        payment_methods=detect_methods(text),
        deadline_text="; ".join(deadlines) if deadlines else None,
        urls=extract_urls(text),
        contact_phones=find_phones(text),
    )
