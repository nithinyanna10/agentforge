"""Minimal JSON Schema subset validation without external jsonschema dependency."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    """Single validation error at a JSON pointer path."""

    path: str
    message: str


class SimpleSchemaValidator:
    """Validate JSON-compatible data against a restricted JSON Schema draft-like spec.

    Supported types: object, array, string, number, integer, boolean, null.
    Supports: properties, required, items, enum, minimum, maximum, minLength, maxLength,
    pattern (string regex), additionalProperties (bool).
    """

    def __init__(self, schema: dict[str, Any]) -> None:
        self._schema = schema

    def validate(self, data: Any) -> list[ValidationIssue]:
        return self._validate(self._schema, data, "$")

    def _validate(self, schema: dict[str, Any], data: Any, path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not isinstance(schema, dict):
            return [ValidationIssue(path, "schema must be an object")]

        if "enum" in schema:
            if data not in schema["enum"]:
                issues.append(ValidationIssue(path, f"value must be one of {schema['enum']!r}"))
            return issues

        stype = schema.get("type")
        if stype is None:
            return issues

        type_ok = self._check_type(stype, data)
        if not type_ok:
            issues.append(ValidationIssue(path, f"expected type {stype!r}, got {self._describe(data)}"))
            return issues

        if stype == "string" and isinstance(data, str):
            issues.extend(self._string_checks(schema, data, path))
        elif stype == "number" and isinstance(data, (int, float)) and not isinstance(data, bool):
            issues.extend(self._number_checks(schema, data, path))
        elif stype == "integer" and isinstance(data, int) and not isinstance(data, bool):
            issues.extend(self._number_checks(schema, float(data), path))
        elif stype == "array" and isinstance(data, list):
            issues.extend(self._array_checks(schema, data, path))
        elif stype == "object" and isinstance(data, dict):
            issues.extend(self._object_checks(schema, data, path))

        return issues

    def _describe(self, data: Any) -> str:
        if isinstance(data, bool):
            return "boolean"
        if data is None:
            return "null"
        return type(data).__name__

    def _check_type(self, stype: str | list[str], data: Any) -> bool:
        if isinstance(stype, list):
            return any(self._check_type(s, data) for s in stype)
        if stype == "null":
            return data is None
        if stype == "boolean":
            return isinstance(data, bool)
        if stype == "string":
            return isinstance(data, str)
        if stype == "number":
            return isinstance(data, (int, float)) and not isinstance(data, bool)
        if stype == "integer":
            return isinstance(data, int) and not isinstance(data, bool)
        if stype == "array":
            return isinstance(data, list)
        if stype == "object":
            return isinstance(data, dict)
        return True

    def _string_checks(self, schema: dict[str, Any], data: str, path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if "minLength" in schema and len(data) < int(schema["minLength"]):
            issues.append(ValidationIssue(path, f"string shorter than minLength {schema['minLength']}"))
        if "maxLength" in schema and len(data) > int(schema["maxLength"]):
            issues.append(ValidationIssue(path, f"string longer than maxLength {schema['maxLength']}"))
        if "pattern" in schema:
            if not re.fullmatch(schema["pattern"], data):
                issues.append(ValidationIssue(path, f"string does not match pattern {schema['pattern']!r}"))
        return issues

    def _number_checks(self, schema: dict[str, Any], data: float, path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if "minimum" in schema and data < float(schema["minimum"]):
            issues.append(ValidationIssue(path, f"value {data} < minimum {schema['minimum']}"))
        if "maximum" in schema and data > float(schema["maximum"]):
            issues.append(ValidationIssue(path, f"value {data} > maximum {schema['maximum']}"))
        return issues

    def _array_checks(self, schema: dict[str, Any], data: list[Any], path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            for i, item in enumerate(data):
                issues.extend(self._validate(items_schema, item, f"{path}[{i}]"))
        return issues

    def _object_checks(self, schema: dict[str, Any], data: dict[str, Any], path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        additional = schema.get("additionalProperties", True)

        for key in required:
            if key not in data:
                issues.append(ValidationIssue(f"{path}.{key}", "missing required property"))

        for key, subschema in props.items():
            if key in data and isinstance(subschema, dict):
                issues.extend(self._validate(subschema, data[key], f"{path}.{key}"))

        extra = set(data.keys()) - set(props.keys())
        if additional is False and extra:
            for k in sorted(extra):
                issues.append(ValidationIssue(f"{path}.{k}", "additional properties not allowed"))

        if isinstance(additional, dict):
            for k in extra:
                issues.extend(self._validate(additional, data[k], f"{path}.{k}"))

        return issues


def validate_json(data: Any, schema: dict[str, Any]) -> list[ValidationIssue]:
    """Convenience: return list of issues (empty if valid)."""
    return SimpleSchemaValidator(schema).validate(data)


def assert_valid(data: Any, schema: dict[str, Any]) -> None:
    """Raise ValueError with joined messages if invalid."""
    issues = validate_json(data, schema)
    if issues:
        msg = "; ".join(f"{i.path}: {i.message}" for i in issues)
        raise ValueError(msg)
