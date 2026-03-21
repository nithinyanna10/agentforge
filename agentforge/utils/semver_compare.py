"""Semantic version parsing and comparison (PEP 440–inspired subset for agent tooling)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Any


@dataclass(frozen=True, order=False)
class SemVer:
    """Major.minor.patch with optional pre-release and build labels."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str | int, ...] = ()
    build: str | None = None

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return _compare_semver(self, other) < 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return _compare_semver(self, other) == 0

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return _compare_semver(self, other) <= 0

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return _compare_semver(self, other) > 0

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return _compare_semver(self, other) >= 0

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.prerelease, self.build))


def _parse_prerelease(s: str) -> tuple[str | int, ...]:
    if not s:
        return ()
    parts: list[str | int] = []
    for part in s.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(part)
    return tuple(parts)


def parse_semver(text: str) -> SemVer:
    """Parse semver-like string; allows leading 'v'."""
    s = text.strip()
    if s.startswith("v") or s.startswith("V"):
        s = s[1:]
    m = re.match(
        r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z\-\.]+))?(?:\+([0-9A-Za-z\-\.]+))?$",
        s,
    )
    if not m:
        raise ValueError(f"not a semver: {text!r}")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    pre = _parse_prerelease(m.group(4) or "")
    build = m.group(5)
    return SemVer(major=major, minor=minor, patch=patch, prerelease=pre, build=build)


def _compare_prerelease(a: tuple[str | int, ...], b: tuple[str | int, ...]) -> int:
    """Return -1,0,1; empty prerelease is greater than any (release > pre)."""
    if not a and not b:
        return 0
    if not a and b:
        return 1
    if a and not b:
        return -1
    n = max(len(a), len(b))
    for i in range(n):
        if i >= len(a):
            return -1
        if i >= len(b):
            return 1
        x, y = a[i], b[i]
        if type(x) != type(y):
            if isinstance(x, int) and isinstance(y, str):
                return -1
            if isinstance(x, str) and isinstance(y, int):
                return 1
        if x < y:
            return -1
        if x > y:
            return 1
    return 0


def _compare_semver(a: SemVer, b: SemVer) -> int:
    if a.major != b.major:
        return -1 if a.major < b.major else 1
    if a.minor != b.minor:
        return -1 if a.minor < b.minor else 1
    if a.patch != b.patch:
        return -1 if a.patch < b.patch else 1
    return _compare_prerelease(a.prerelease, b.prerelease)


def satisfies_range(version: str, spec: str) -> bool:
    """Very small subset: '>=1.2.3', '<=2.0.0', '^1.2.3', '~1.2.3', exact match."""
    v = parse_semver(version)
    spec = spec.strip()
    if spec.startswith(">="):
        lo = parse_semver(spec[2:].strip())
        return v >= lo
    if spec.startswith("<="):
        hi = parse_semver(spec[2:].strip())
        return v <= hi
    if spec.startswith(">"):
        lo = parse_semver(spec[1:].strip())
        return v > lo
    if spec.startswith("<"):
        hi = parse_semver(spec[1:].strip())
        return v < hi
    if spec.startswith("^"):
        base = parse_semver(spec[1:].strip())
        upper = SemVer(base.major + 1, 0, 0)
        return base <= v < upper
    if spec.startswith("~"):
        base = parse_semver(spec[1:].strip())
        upper = SemVer(base.major, base.minor + 1, 0)
        return base <= v < upper
    return v == parse_semver(spec)


def bump_major(v: SemVer) -> SemVer:
    return SemVer(v.major + 1, 0, 0)


def bump_minor(v: SemVer) -> SemVer:
    return SemVer(v.major, v.minor + 1, 0)


def bump_patch(v: SemVer) -> SemVer:
    return SemVer(v.major, v.minor, v.patch + 1)


@total_ordering
class LooseVersion:
    """Fallback for non-semver strings (lexicographic compare)."""

    def __init__(self, s: str) -> None:
        self._s = s

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LooseVersion):
            return NotImplemented
        return self._s == other._s

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, LooseVersion):
            return NotImplemented
        return self._s < other._s


def safe_parse_semver(text: str) -> SemVer | None:
    """Return SemVer or None if parsing fails."""
    try:
        return parse_semver(text)
    except ValueError:
        return None