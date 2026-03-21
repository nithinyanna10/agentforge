"""Tests for semver_compare utilities."""

from __future__ import annotations

import pytest

from agentforge.utils import semver_compare as semver


def test_parse_and_order() -> None:
    a = semver.parse_semver("1.0.0")
    b = semver.parse_semver("1.0.1")
    assert a < b
    assert semver.parse_semver("v2.0.0") == semver.parse_semver("2.0.0")


def test_prerelease_order() -> None:
    rel = semver.parse_semver("1.0.0")
    rc = semver.parse_semver("1.0.0-rc.1")
    assert rc < rel


def test_prerelease_numeric_vs_alpha() -> None:
    a = semver.parse_semver("1.0.0-1")
    b = semver.parse_semver("1.0.0-alpha")
    assert a < b


def test_ranges() -> None:
    assert semver.satisfies_range("1.5.0", ">=1.0.0")
    assert semver.satisfies_range("1.5.0", "^1.2.0")
    assert not semver.satisfies_range("2.0.0", "^1.2.0")
    assert semver.satisfies_range("1.2.5", "~1.2.3")


def test_bumps() -> None:
    v = semver.parse_semver("1.2.3")
    assert semver.bump_major(v).major == 2
    assert semver.bump_minor(v).minor == 3
    assert semver.bump_patch(v).patch == 4


def test_parse_invalid() -> None:
    with pytest.raises(ValueError):
        semver.parse_semver("not-a-version")


def test_safe_parse() -> None:
    assert semver.safe_parse_semver("bad") is None
    assert semver.safe_parse_semver("1.0.0") is not None


def test_loose_version() -> None:
    x = semver.LooseVersion("a")
    y = semver.LooseVersion("b")
    assert x < y


def test_eq_hash() -> None:
    a = semver.parse_semver("1.0.0")
    b = semver.parse_semver("1.0.0")
    assert a == b
    assert hash(a) == hash(b)
