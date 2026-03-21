"""Tests for chrono utilities."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from agentforge.utils import chrono


def test_parse_relative_in_hours() -> None:
    anchor = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
    r = chrono.parse_relative_time("in 2 hours", now=anchor)
    assert r.resolved == anchor + timedelta(hours=2)


def test_parse_relative_ago() -> None:
    anchor = datetime(2020, 1, 10, 0, 0, 0, tzinfo=UTC)
    r = chrono.parse_relative_time("3 days ago", now=anchor)
    assert r.resolved == anchor - timedelta(days=3)


def test_parse_relative_compact() -> None:
    anchor = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    r = chrono.parse_relative_time("-30m", now=anchor)
    assert r.resolved == anchor - timedelta(minutes=30)


def test_parse_relative_invalid() -> None:
    with pytest.raises(ValueError):
        chrono.parse_relative_time("not a phrase", now=datetime.now(tz=UTC))


def test_parse_iso8601_z() -> None:
    dt = chrono.parse_iso8601_utc("2024-05-01T12:00:00Z")
    assert dt.tzinfo == UTC


def test_format_rfc3339() -> None:
    dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    s = chrono.format_rfc3339(dt)
    assert s.endswith("Z") or "+00:00" in s


def test_business_days_add_forward() -> None:
    # Monday 2024-01-08
    start = date(2024, 1, 8)
    end = chrono.business_days_add(start, 4)
    assert end.weekday() < 5


def test_business_days_add_negative() -> None:
    start = date(2024, 1, 12)  # Friday
    end = chrono.business_days_add(start, -1)
    assert end.weekday() < 5


def test_quarter_of_year() -> None:
    assert chrono.quarter_of_year(date(2024, 2, 1)) == "Q1"
    assert chrono.quarter_of_year(date(2024, 11, 1)) == "Q4"


def test_merge_intervals_empty() -> None:
    assert chrono.merge_intervals([]) == []


def test_merge_intervals_overlap() -> None:
    a = datetime(2024, 1, 1, tzinfo=UTC)
    b = datetime(2024, 1, 5, tzinfo=UTC)
    c = datetime(2024, 1, 3, tzinfo=UTC)
    d = datetime(2024, 1, 10, tzinfo=UTC)
    m = chrono.merge_intervals([(a, b), (c, d)])
    assert len(m) == 1
    assert m[0][0] == a
    assert m[0][1] == d


def test_human_duration() -> None:
    assert "1h" in chrono.human_duration(timedelta(hours=1, minutes=2))


def test_localize_weekday_known_tz() -> None:
    w, d = chrono.localize_weekday(date(2024, 6, 15), "America/Los_Angeles")
    assert len(w) > 0
    assert len(d) == 10
