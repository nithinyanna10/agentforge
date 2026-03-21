"""Tests for simple_schema validation."""

from __future__ import annotations

import pytest

from agentforge.utils.simple_schema import SimpleSchemaValidator, assert_valid, validate_json


def test_object_required() -> None:
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    }
    issues = validate_json({}, schema)
    assert any("name" in i.path for i in issues)


def test_string_pattern() -> None:
    schema = {"type": "string", "pattern": r"^[a-z]+$"}
    assert validate_json("abc", schema) == []
    assert validate_json("A", schema) != []


def test_nested_object() -> None:
    schema = {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "properties": {"age": {"type": "integer", "minimum": 0}},
                "required": ["age"],
            }
        },
        "required": ["user"],
    }
    issues = validate_json({"user": {"age": -1}}, schema)
    assert issues


def test_array_items() -> None:
    schema = {"type": "array", "items": {"type": "integer"}}
    issues = validate_json([1, "x"], schema)
    assert issues


def test_enum() -> None:
    schema = {"enum": ["a", "b"]}
    assert validate_json("a", schema) == []
    assert validate_json("c", schema) != []


def test_assert_valid_raises() -> None:
    schema = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}
    with pytest.raises(ValueError):
        assert_valid({}, schema)


def test_validator_union_type_list() -> None:
    schema = {"type": ["string", "null"]}
    assert SimpleSchemaValidator(schema).validate(None) == []
    assert SimpleSchemaValidator(schema).validate("hi") == []
