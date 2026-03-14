"""Regex tool — search and replace using regular expressions."""

from __future__ import annotations

import re
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class RegexTool(Tool):
    """Apply a regex to text: find matches or perform replace."""

    @property
    def name(self) -> str:
        return "regex"

    @property
    def description(self) -> str:
        return (
            "Apply a regular expression to text. Mode: 'find' returns all matches (or first N); "
            "'replace' substitutes pattern with replacement string."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input text."},
                "pattern": {"type": "string", "description": "Regular expression pattern."},
                "mode": {
                    "type": "string",
                    "enum": ["find", "replace"],
                    "description": "Either find matches or replace.",
                },
                "replacement": {"type": "string", "description": "Replacement string (for mode replace).", "default": ""},
                "max_matches": {
                    "type": "integer",
                    "description": "Max number of matches to return for find (default 20).",
                    "default": 20,
                },
                "ignore_case": {"type": "boolean", "description": "Case-insensitive matching.", "default": False},
            },
            "required": ["text", "pattern", "mode"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text") or ""
        pattern = kwargs.get("pattern") or ""
        mode = (kwargs.get("mode") or "find").lower()
        replacement = kwargs.get("replacement", "")
        max_matches = max(1, min(100, int(kwargs.get("max_matches", 20))))
        ignore_case = bool(kwargs.get("ignore_case", False))

        if not pattern:
            return ToolResult(success=False, output="", error="Pattern is required.")

        try:
            flags = re.IGNORECASE if ignore_case else 0
            rx = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(success=False, output="", error=f"Invalid regex: {e}")

        try:
            if mode == "find":
                matches = rx.findall(text)
                matches = matches[:max_matches]
                out = "\n".join(str(m) for m in matches) if matches else "(no matches)"
                return ToolResult(success=True, output=out, metadata={"count": len(matches)})
            elif mode == "replace":
                out = rx.sub(replacement, text)
                return ToolResult(success=True, output=out, metadata={"mode": "replace"})
            else:
                return ToolResult(success=False, output="", error="Mode must be 'find' or 'replace'.")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
