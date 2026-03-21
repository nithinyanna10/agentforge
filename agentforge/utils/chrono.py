"""Relative time parsing and timezone-aware helpers (lightweight, English-friendly)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, available_timezones


@dataclass(frozen=True)
class RelativeTimeResult:
    """Outcome of parsing a relative time phrase."""

    anchor: datetime
    resolved: datetime
    delta: timedelta
    matched: str


_RELATIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\s*in\s+(\d+)\s+(second|seconds|minute|minutes|hour|hours|day|days|week|weeks)\s*$", re.I), "in"),
    (re.compile(r"^\s*(\d+)\s+(second|seconds|minute|minutes|hour|hours|day|days|week|weeks)\s+ago\s*$", re.I), "ago"),
    (re.compile(r"^\s*(\+|-)\s*(\d+)\s*(s|sec|m|min|h|hr|d|w)\s*$", re.I), "compact"),
]


def _unit_to_seconds(unit: str) -> int:
    u = unit.lower().rstrip("s")
    if u in ("second", "sec"):
        return 1
    if u in ("minute", "min", "m"):
        return 60
    if u in ("hour", "h", "hr"):
        return 3600
    if u in ("day", "d"):
        return 86400
    if u in ("week", "w"):
        return 86400 * 7
    raise ValueError(f"unknown unit: {unit}")


def parse_relative_time(
    phrase: str,
    *,
    now: datetime | None = None,
) -> RelativeTimeResult:
    """Parse a small set of English relative phrases into an absolute UTC datetime.

    Supported examples:
    - "in 2 hours", "in 30 minutes"
    - "3 days ago"
    - "+10m", "-2h", "+1d" (compact)
    """
    if now is None:
        now = datetime.now(tz=UTC)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    text = phrase.strip()
    if not text:
        raise ValueError("empty phrase")

    for pat, kind in _RELATIVE_PATTERNS:
        m = pat.match(text)
        if not m:
            continue
        if kind == "in":
            n = int(m.group(1))
            unit = m.group(2)
            sec = n * _unit_to_seconds(unit)
            delta = timedelta(seconds=sec)
            return RelativeTimeResult(anchor=now, resolved=now + delta, delta=delta, matched=m.group(0))
        if kind == "ago":
            n = int(m.group(1))
            unit = m.group(2)
            sec = n * _unit_to_seconds(unit)
            delta = timedelta(seconds=sec)
            return RelativeTimeResult(anchor=now, resolved=now - delta, delta=delta, matched=m.group(0))
        if kind == "compact":
            sign = -1 if m.group(1) == "-" else 1
            n = int(m.group(2))
            suf = m.group(3).lower()
            unit_map = {"s": "second", "sec": "second", "m": "minute", "min": "minute", "h": "hour", "hr": "hour", "d": "day", "w": "week"}
            unit = unit_map.get(suf, "second")
            sec = sign * n * _unit_to_seconds(unit)
            delta = timedelta(seconds=sec)
            return RelativeTimeResult(anchor=now, resolved=now + delta, delta=delta, matched=m.group(0))

    raise ValueError(f"unsupported relative phrase: {phrase!r}")


def parse_iso8601_utc(value: str) -> datetime:
    """Parse ISO8601 datetime; assume UTC if no tz."""
    s = value.strip()
    if not s:
        raise ValueError("empty datetime")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_rfc3339(dt: datetime) -> str:
    """Format datetime as RFC3339 in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    u = dt.astimezone(UTC)
    s = u.isoformat(timespec="seconds")
    return s.replace("+00:00", "Z")


def weekday_name(d: date | datetime) -> str:
    """Return English weekday name."""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%A")


def localize_weekday(
    d: date | datetime,
    tz_name: str,
) -> tuple[str, str]:
    """Return (weekday_name, local_iso_date) in the given IANA timezone."""
    if tz_name not in available_timezones():
        raise ValueError(f"unknown timezone: {tz_name}")
    tz = ZoneInfo(tz_name)
    if isinstance(d, date) and not isinstance(d, datetime):
        dt = datetime.combine(d, datetime.min.time(), tzinfo=UTC)
    else:
        dt = d
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    local = dt.astimezone(tz)
    return local.strftime("%A"), local.date().isoformat()


def business_days_add(start: date, days: int) -> date:
    """Add N calendar days skipping weekends (Mon–Fri only). Negative days supported."""
    if days == 0:
        return start
    step = 1 if days > 0 else -1
    remaining = abs(days)
    cur = start
    while remaining > 0:
        cur += timedelta(days=step)
        if cur.weekday() < 5:
            remaining -= 1
    return cur


def quarter_of_year(d: date | datetime) -> str:
    """Return 'Q1'..'Q4' for a year."""
    if isinstance(d, datetime):
        d = d.date()
    q = (d.month - 1) // 3 + 1
    return f"Q{q}"


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Merge overlapping [start, end) intervals in UTC."""
    if not intervals:
        return []
    norm: list[tuple[datetime, datetime]] = []
    for a, b in intervals:
        if a.tzinfo is None:
            a = a.replace(tzinfo=UTC)
        if b.tzinfo is None:
            b = b.replace(tzinfo=UTC)
        if b <= a:
            continue
        norm.append((a.astimezone(UTC), b.astimezone(UTC)))
    if not norm:
        return []
    norm.sort(key=lambda x: x[0])
    merged: list[tuple[datetime, datetime]] = []
    cur_s, cur_e = norm[0]
    for s, e in norm[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged


def human_duration(delta: timedelta) -> str:
    """Approximate English duration string."""
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return sign + " ".join(parts)


def coerce_dict_datetimes(obj: Any) -> Any:
    """Recursively convert ISO8601 strings in dict/list to datetime (best-effort)."""
    if isinstance(obj, dict):
        return {k: coerce_dict_datetimes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [coerce_dict_datetimes(v) for v in obj]
    if isinstance(obj, str) and len(obj) >= 10 and obj[4] == "-" and obj[7] == "-":
        try:
            return parse_iso8601_utc(obj)
        except ValueError:
            return obj
    return obj
