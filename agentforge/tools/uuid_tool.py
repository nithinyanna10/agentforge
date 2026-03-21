"""UUID generation, parsing, and validation."""

from __future__ import annotations

import uuid
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class UuidTool(Tool):
    """Generate RFC 4122 UUIDs (v4 random, v7 time-ordered when available) and inspect strings."""

    @property
    def name(self) -> str:
        return "uuid_tool"

    @property
    def description(self) -> str:
        return (
            "Create UUIDs (v4 random; v7 if Python supports it), parse a string into fields, "
            "or validate UUID format."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["uuid4", "uuid7", "parse", "validate"],
                },
                "value": {
                    "type": "string",
                    "description": "UUID string for parse/validate.",
                },
                "count": {
                    "type": "integer",
                    "description": "For uuid4/uuid7: how many to generate (default 1, max 100).",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "uuid4").strip().lower()
        value = kwargs.get("value")
        count = int(kwargs.get("count") or 1)
        count = max(1, min(100, count))

        if action == "uuid4":
            ids = [str(uuid.uuid4()) for _ in range(count)]
            out = "\n".join(ids) if count > 1 else ids[0]
            return ToolResult(success=True, output=out, metadata={"version": 4, "count": count})

        if action == "uuid7":
            gen7 = getattr(uuid, "uuid7", None)
            if gen7 is None:
                return ToolResult(
                    success=False,
                    output="",
                    error="uuid7 is not available in this Python version.",
                )
            ids = [str(gen7()) for _ in range(count)]
            out = "\n".join(ids) if count > 1 else ids[0]
            return ToolResult(success=True, output=out, metadata={"version": 7, "count": count})

        if action in ("parse", "validate"):
            if value is None or not str(value).strip():
                return ToolResult(success=False, output="", error="value is required.")
            s = str(value).strip()
            try:
                u = uuid.UUID(s)
            except ValueError as e:
                return ToolResult(success=False, output="", error=f"Invalid UUID: {e}")
            if action == "validate":
                return ToolResult(success=True, output="valid", metadata={"canonical": str(u)})
            return ToolResult(
                success=True,
                output=(
                    f"hex={u.hex}\n"
                    f"urn={u.urn}\n"
                    f"version={u.version}\n"
                    f"variant={u.variant}\n"
                    f"int={u.int}"
                ),
                metadata={
                    "hex": u.hex,
                    "version": u.version,
                    "variant": str(u.variant),
                },
            )

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")
