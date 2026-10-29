"""Temporal selection: half-open validity intervals and the recorded-time axis."""
from __future__ import annotations

from datetime import timedelta

from hypothesis import given
from hypothesis import strategies as st

from policyguard.domain.model import ApprovalStatus
from policyguard.domain.temporal import HalfOpenIntervalSelector, LatestRecordedSelector, contains, known_at

from .factories import utc, version


def test_interval_is_half_open():
    v = version(valid_from=utc(2026, 1, 1), valid_to=utc(2026, 9, 1))
    assert contains(v, utc(2026, 1, 1)) is True            # valid_from included
    assert contains(v, utc(2026, 8, 31, 23)) is True
    assert contains(v, utc(2026, 9, 1)) is False           # valid_to excluded
    assert contains(v, utc(2025, 12, 31, 23)) is False


def test_null_valid_to_means_open_but_unknown_end():
    v = version(valid_from=utc(2026, 1, 1), valid_to=None)
    assert contains(v, utc(2030, 1, 1)) is True


def test_unknown_valid_from_is_not_assumed():
    v = version(valid_from=None)
    assert contains(v, utc(2026, 5, 1)) is None


def test_recorded_time_axis_hides_versions_recorded_later():
    v = version(recorded_at=utc(2026, 10, 1))
    assert known_at(v, utc(2026, 9, 30)) is False
    assert known_at(v, utc(2026, 10, 1)) is True


def test_revoked_versions_are_not_known_after_revocation():
    v = version(revoked_at=utc(2026, 10, 1))
    assert known_at(v, utc(2026, 9, 30)) is True
    assert known_at(v, utc(2026, 10, 1)) is False


def test_selector_ignores_unapproved_versions():
    sel = HalfOpenIntervalSelector().select([version(approval_status=ApprovalStatus.DISCOVERED)], utc(2026, 5, 1),
                                            utc(2026, 10, 28))
    assert sel.applicable == ()


def test_selector_reports_unknown_dates_separately():
    sel = HalfOpenIntervalSelector().select([version(valid_from=None)], utc(2026, 5, 1), utc(2026, 10, 28))
    assert sel.applicable == () and [v.version_id for v in sel.validity_unknown] == ["v1"]


def test_baseline_selector_picks_latest_regardless_of_date():
    old = version("v1", valid_from=utc(2026, 1, 1), valid_to=utc(2026, 9, 1))
    new = version("v2", valid_from=utc(2026, 9, 1), recorded_at=utc(2026, 8, 20))
    sel = LatestRecordedSelector().select([old, new], utc(2026, 3, 1), utc(2026, 10, 28))
    assert [v.version_id for v in sel.applicable] == ["v2"]


@given(st.integers(min_value=0, max_value=3 * 365 * 24))
def test_consecutive_versions_select_exactly_one(hours):
    boundary = utc(2026, 9, 1)
    old = version("v1", valid_from=utc(2026, 1, 1), valid_to=boundary)
    new = version("v2", valid_from=boundary, valid_to=None)
    t = utc(2026, 1, 1) + timedelta(hours=hours)
    sel = HalfOpenIntervalSelector().select([old, new], t, utc(2030, 1, 1))
    expected = "v1" if t < boundary else "v2"
    assert [v.version_id for v in sel.applicable] == [expected]
