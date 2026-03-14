"""JSONPath / JSON query tool — extract values from JSON using path expressions."""

from __future__ import annotations

import json
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class JSONPathTool(Tool):
    """Extract values from JSON text using simple path syntax (e.g. $.foo.bar, $.items[0])."""

    @property
    def name(self) -> str:
        return "json_path"

    @property
    def description(self) -> str:
        return (
            "Query JSON with a path. Path format: $.key.nested, $.array[0], $.items[*].name. "
            "Returns the value(s) at that path as JSON string."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "json_text": {"type": "string", "description": "The JSON string to query."},
                "path": {"type": "string", "description": "Path expression (e.g. $.data.items[0].name)."},
            },
            "required": ["json_text", "path"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        json_text = kwargs.get("json_text") or ""
        path = (kwargs.get("path") or "").strip()

        if not path.startswith("$"):
            return ToolResult(success=False, output="", error="Path must start with $.")

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            return ToolResult(success=False, output="", error=f"Invalid JSON: {e}")

        try:
            value = self._get_path(data, path)
            out = json.dumps(value, indent=2) if value is not None else "null"
            return ToolResult(success=True, output=out, metadata={"path": path})
        except (KeyError, IndexError, TypeError) as e:
            return ToolResult(success=False, output="", error=f"Path error: {e}")

    def _get_path(self, obj: Any, path: str) -> Any:
        """Simple path evaluator: $.a.b.c, $.arr[0], $.arr[*]."""
        parts = path.strip().replace("$.", "").replace("$", "").split(".")
        if not parts or (len(parts) == 1 and not parts[0]):
            return obj
        current = obj
        for part in parts:
            if not part:
                continue
            if "[" in part:
                key, rest = part.split("[", 1)
                if key:
                    current = current[key]
                idx = rest.rstrip("]")
                if idx == "*":
                    if isinstance(current, list):
                        return [self._get_path(c, "." + ".".join(parts[parts.index(part) + 1 :])) for c in current]
                    return current
                current = current[int(idx)]
            else:
                current = current[part]
        return current
