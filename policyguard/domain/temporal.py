"""Temporal policy selection.

Two time axes:

* valid time: when a policy applies. Half-open interval ``valid_from <= t < valid_to``.
  ``valid_to = None`` means the end is not known. ``valid_from = None`` means the
  start is unknown, so the version cannot be applied to any date.
* recorded time: when the system learned about a version (``recorded_at``) and
  when it stopped trusting it (``revoked_at``). ``as_of`` picks a point on this axis.

Selection strategies implement ``TemporalSelector``. ``HalfOpenIntervalSelector`` is
the product rule. ``LatestRecordedSelector`` exists only as the evaluation baseline
("plain retrieval picks the newest document") and is never used for decisions.
Complexity: O(n) per call over the candidate versions of one institution; candidates
come from an indexed query on (institution_id, policy_id, valid_from).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .model import ApprovalStatus, PolicyVersion


def contains(v: PolicyVersion, t: datetime) -> bool | None:
    """True/False for a known interval; None when the start of validity is unknown."""
    if v.valid_from is None:
        return None
    if t < v.valid_from:
        return False
    return v.valid_to is None or t < v.valid_to


def known_at(v: PolicyVersion, as_of: datetime) -> bool:
    return v.recorded_at <= as_of and (v.revoked_at is None or v.revoked_at > as_of)


def _usable(versions: Iterable[PolicyVersion], as_of: datetime) -> list[PolicyVersion]:
    return [v for v in versions if v.approval_status is ApprovalStatus.APPROVED and known_at(v, as_of)]


def _order(vs: Iterable[PolicyVersion]) -> tuple[PolicyVersion, ...]:
    return tuple(sorted(vs, key=lambda v: (v.policy_id, v.valid_from or datetime.min.replace(tzinfo=None)
                                           if v.valid_from is None else v.valid_from.replace(tzinfo=None),
                                           v.version_id)))


@dataclass(frozen=True)
class Selection:
    applicable: tuple[PolicyVersion, ...]
    validity_unknown: tuple[PolicyVersion, ...]
    ended_before: tuple[PolicyVersion, ...]   # usable versions whose validity ended at or before t


class TemporalSelector(Protocol):
    def select(self, versions: Iterable[PolicyVersion], t: datetime, as_of: datetime) -> Selection: ...


class HalfOpenIntervalSelector:
    def select(self, versions: Iterable[PolicyVersion], t: datetime, as_of: datetime) -> Selection:
        usable = _usable(versions, as_of)
        return Selection(
            applicable=_order(v for v in usable if contains(v, t) is True),
            validity_unknown=_order(v for v in usable if contains(v, t) is None),
            ended_before=_order(v for v in usable if v.valid_to is not None and v.valid_to <= t))


class LatestRecordedSelector:
    """Evaluation baseline only: newest recorded version, validity ignored."""

    def select(self, versions: Iterable[PolicyVersion], t: datetime, as_of: datetime) -> Selection:
        usable = sorted(_usable(versions, as_of), key=lambda v: v.recorded_at, reverse=True)
        return Selection(applicable=tuple(usable[:1]), validity_unknown=(), ended_before=())
