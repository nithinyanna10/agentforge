"""Tests for pipeline_conditions."""

from __future__ import annotations

import pytest
from agentforge.core.pipeline_conditions import compile_condition


def test_condition_true() -> None:
    fn = compile_condition("true")
    assert fn({}) is True
    assert fn({"x": 1}) is True


def test_condition_key() -> None:
    fn = compile_condition("skip")
    assert fn({}) is False
    assert fn({"skip": True}) is True
    assert fn({"skip": 1}) is True


def test_condition_not_key() -> None:
    fn = compile_condition("not skip")
    assert fn({}) is True
    assert fn({"skip": True}) is False
    assert fn({"skip": False}) is True
