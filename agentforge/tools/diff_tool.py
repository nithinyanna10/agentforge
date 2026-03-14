"""Diff tool — compare two texts and return unified diff or summary (next-level)."""

from __future__ import annotations

import difflib
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class DiffTool(Tool):
    """Compare two text strings and return unified diff or a brief summary of changes."""

    @property
    def name(self) -> str:
        return "diff_text"

    @property
    def description(self) -> str:
        return (
            "Compare two texts (old vs new). Returns unified diff by default, "
            "or set output=summary for a short change summary (additions/deletions count)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "old_text": {"type": "string", "description": "Original text."},
                "new_text": {"type": "string", "description": "New text to compare against."},
                "output": {
                    "type": "string",
                    "enum": ["diff", "summary"],
                    "description": "Return full unified diff or a short summary.",
                    "default": "diff",
                },
            },
            "required": ["old_text", "new_text"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        old_text = kwargs.get("old_text") or ""
        new_text = kwargs.get("new_text") or ""
        output_mode = (kwargs.get("output") or "diff").strip().lower()

        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        if output_mode == "summary":
            matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
            add_count = sum(t[2] - t[1] for t in matcher.get_opcodes() if t[0] == "insert")
            del_count = sum(t[2] - t[1] for t in matcher.get_opcodes() if t[0] == "delete")
            out = f"Lines added: {add_count}, Lines removed: {del_count}, Ratio: {matcher.ratio():.2f}"
            return ToolResult(success=True, output=out, metadata={"additions": add_count, "deletions": del_count})

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="old",
            tofile="new",
            lineterm="",
        )
        out = "\n".join(diff)
        return ToolResult(success=True, output=out or "(no diff)", metadata={"output": "diff"})
