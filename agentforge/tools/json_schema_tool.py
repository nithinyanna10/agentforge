"""Validate JSON against a simple JSON-schema subset (see utils.simple_schema)."""

from __future__ import annotations

import json
from typing import Any

from agentforge.tools.base import Tool, ToolResult
from agentforge.utils.simple_schema import SimpleSchemaValidator, ValidationIssue


class JsonSchemaTool(Tool):
    """Validate JSON data with a restricted JSON Schema object (types, required, properties, etc.)."""

    @property
    def name(self) -> str:
        return "json_schema_validate"

    @property
    def description(self) -> str:
        return (
            "Validate JSON against a simple JSON Schema (object/array/string/number/integer/boolean/null, "
            "required, properties, items, enum, min/max, pattern). Returns errors or ok."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data_json": {"type": "string", "description": "JSON string to validate."},
                "schema_json": {"type": "string", "description": "JSON Schema object as string."},
            },
            "required": ["data_json", "schema_json"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        data_raw = kwargs.get("data_json")
        schema_raw = kwargs.get("schema_json")
        if data_raw is None or schema_raw is None:
            return ToolResult(success=False, output="", error="data_json and schema_json are required.")

        try:
            data = json.loads(str(data_raw))
        except json.JSONDecodeError as e:
            return ToolResult(success=False, output="", error=f"data_json invalid: {e}")

        try:
            schema = json.loads(str(schema_raw))
        except json.JSONDecodeError as e:
            return ToolResult(success=False, output="", error=f"schema_json invalid: {e}")

        if not isinstance(schema, dict):
            return ToolResult(success=False, output="", error="schema_json must be a JSON object.")

        issues: list[ValidationIssue] = SimpleSchemaValidator(schema).validate(data)
        if not issues:
            return ToolResult(success=True, output="ok", metadata={"valid": True})

        lines = [f"{i.path}: {i.message}" for i in issues]
        return ToolResult(
            success=False,
            output="\n".join(lines),
            error="validation_failed",
            metadata={"valid": False, "issue_count": len(issues)},
        )
