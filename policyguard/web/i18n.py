"""Externalized interface strings. English is the default locale; other catalogs are optional overlays.

Institutional evidence is never translated through this catalog: quotes stay in their original language and
any translation is shown with an explicit label.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

MESSAGES_DIR = Path(__file__).parent / "messages"
DEFAULT_LOCALE = "en"


@lru_cache(maxsize=8)
def catalog(locale: str = DEFAULT_LOCALE) -> dict:
    base = json.loads((MESSAGES_DIR / f"{DEFAULT_LOCALE}.json").read_text())
    path = MESSAGES_DIR / f"{locale}.json"
    if locale != DEFAULT_LOCALE and path.is_file():
        base = {**base, **json.loads(path.read_text())}   # missing keys fall back to English
    return base


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def t(key: str, locale: str = DEFAULT_LOCALE, **params) -> str:
    value = catalog(locale).get(key)
    if value is None:
        raise KeyError(f"missing message: {key}")
    return value.format_map(_Safe(params)) if params else value


def tn(key: str, n: int, locale: str = DEFAULT_LOCALE) -> str:
    """Counted message: uses `<key>.one` for n == 1 when the catalog has it, else `<key>`."""
    return t(f"{key}.one" if n == 1 and has(f"{key}.one", locale) else key, locale, n=n)


def has(key: str, locale: str = DEFAULT_LOCALE) -> bool:
    return key in catalog(locale)
