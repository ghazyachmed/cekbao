"""Normalization used before comparing instruction values with policy values."""
from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def account(value: str) -> str:
    """IBAN/account numbers: drop spaces, dashes and dots; compare case-insensitively."""
    return re.sub(r"[^0-9A-Za-z]", "", value).upper()


def name(value: str) -> str:
    """Names: Unicode NFKC, case-folded, punctuation and repeated spaces removed."""
    folded = unicodedata.normalize("NFKC", value).casefold()
    return _NON_ALNUM.sub(" ", folded).strip()


def code(value: str) -> str:
    return value.strip().upper()
