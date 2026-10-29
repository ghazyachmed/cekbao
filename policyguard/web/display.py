"""Domain-to-display mapping. One place decides how a decision, state or reason is worded and styled."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .i18n import catalog, has, t

DECISION_TONE = {"CONSISTENT": "ok", "CONFLICT": "bad", "INSUFFICIENT_EVIDENCE": "warn", "REQUIRES_REVIEW": "review"}
DECISION_ICON = {"CONSISTENT": "check", "CONFLICT": "stop", "INSUFFICIENT_EVIDENCE": "question",
                 "REQUIRES_REVIEW": "person"}
STATE_TONE = {"ACCEPTED": "info", "QUEUED": "info", "PROCESSING": "info", "RETRY_WAIT": "warn",
              "COMPLETED": "ok", "FAILED": "bad", "DEAD_LETTER": "bad", "CANCELLED": "neutral"}
DONE_STATES = {"COMPLETED", "FAILED", "DEAD_LETTER", "CANCELLED"}


def decision(value: str) -> dict:
    return {"value": value, "label": t(f"decision.{value}"), "tone": DECISION_TONE[value], "icon": DECISION_ICON[value]}


def job_state(state: str, retry_at: str | None = None) -> dict:
    when = timestamp_label(retry_at) if retry_at else ""
    return {"state": state, "label": t(f"state.{state}.label"), "description": t(f"state.{state}.description", time=when),
            "tone": STATE_TONE.get(state, "neutral"), "done": state in DONE_STATES}


def next_action(value: str, institution: str | None) -> str:
    return t(f"next.{value}", institution=institution or "the institution")


def channel(value: str | None) -> str:
    if not value:
        return ""
    return ", ".join(t(f"channel.{v.strip()}") if has(f"channel.{v.strip()}") else v for v in value.split(","))


def reason(finding: dict) -> str:
    found, expected = finding.get("found"), finding.get("expected")
    if finding.get("field") == "channel":
        found, expected = channel(found), channel(expected)
    return t(f"reason.{finding['reason']}", found=found or "", expected=expected or "")


def evidence_level(value: str | None) -> dict:
    key = value or "NONE"
    return {"value": key, "label": t(f"level.{key}"), "description": t(f"level.{key}.description")}


def limitation(value: str) -> str:
    return t(f"limitation.{value}")


def _parse(value) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def date_label(value, tz: str | None = None) -> str:
    if not value:
        return ""
    d = _parse(value)
    if tz:
        d = d.astimezone(ZoneInfo(tz))
    return f"{d.day} {catalog()['months'][d.month - 1]} {d.year}"


def timestamp_label(value, tz: str = "UTC") -> str:
    if not value:
        return ""
    d = _parse(value).astimezone(ZoneInfo(tz))
    suffix = "UTC" if tz == "UTC" else tz
    return f"{date_label(d)}, {d:%H:%M} {suffix}"


def inference(info: dict | None) -> str:
    if not info:
        return ""
    mode = info.get("mode", "rules")
    latency = f"{info['latency_ms'] / 1000:.1f} s" if info.get("latency_ms") is not None else "n/a"
    return t(f"inference.{mode}", model=info.get("model_id", ""), latency=latency)


def date_iso(value, tz: str | None) -> str:
    """The calendar date (YYYY-MM-DD) of a stored UTC instant in the case time zone, for refilling forms."""
    if not value:
        return ""
    d = _parse(value)
    return (d.astimezone(ZoneInfo(tz)) if tz else d).date().isoformat()


def is_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False
