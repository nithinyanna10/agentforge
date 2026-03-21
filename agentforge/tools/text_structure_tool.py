"""Structured text analysis tool — code fences, headings, links, stats."""

from __future__ import annotations

import json
from typing import Any

from agentforge.tools.base import Tool, ToolResult
from agentforge.utils import structured_text as st


class TextStructureTool(Tool):
    """Analyze text structure: Markdown headings, links, fenced code, bullets, reading time."""

    @property
    def name(self) -> str:
        return "text_structure"

    @property
    def description(self) -> str:
        return (
            "Analyze unstructured or Markdown text: extract headings, links, code blocks, "
            "outline tree, bullet lines, word count, reading time, and full stats JSON."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "stats",
                        "headings",
                        "links",
                        "code_fences",
                        "outline",
                        "bullets",
                        "numbered",
                        "strip_inline_md",
                    ],
                },
                "text": {"type": "string", "description": "Input document text."},
            },
            "required": ["action", "text"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "stats").strip().lower()
        text = kwargs.get("text") or ""

        if action == "stats":
            return ToolResult(success=True, output=json.dumps(st.text_stats(text), indent=2))

        if action == "headings":
            hs = st.extract_markdown_headings(text)
            data = [{"level": h.level, "text": h.text, "line": h.line_index + 1} for h in hs]
            return ToolResult(success=True, output=json.dumps(data, indent=2))

        if action == "links":
            ls = st.extract_markdown_links(text)
            data = [{"text": x.text, "url": x.url, "line": x.line_index + 1} for x in ls]
            return ToolResult(success=True, output=json.dumps(data, indent=2))

        if action == "code_fences":
            blocks = st.extract_fenced_code_blocks(text)
            data = [
                {
                    "language": b.language,
                    "lines": f"{b.start_line}-{b.end_line}",
                    "body_preview": b.body[:2000],
                }
                for b in blocks
            ]
            return ToolResult(success=True, output=json.dumps(data, indent=2))

        if action == "outline":
            hs = st.extract_markdown_headings(text)
            tree = st.build_heading_outline(hs)
            return ToolResult(success=True, output=st.outline_to_text(tree))

        if action == "bullets":
            items = st.extract_bullet_lines(text)
            return ToolResult(success=True, output=json.dumps(items, indent=2))

        if action == "numbered":
            items = st.extract_numbered_items(text)
            return ToolResult(success=True, output=json.dumps(items, indent=2))

        if action == "strip_inline_md":
            return ToolResult(success=True, output=st.strip_markdown_inline(text))

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")
