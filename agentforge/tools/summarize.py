"""Summarization tool — condense long text into configurable summaries."""

from __future__ import annotations

import re
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class SummarizeTool(Tool):
    """Summarize long text by extracting key sentences or truncating with ellipsis."""

    @property
    def name(self) -> str:
        return "summarize"

    @property
    def description(self) -> str:
        return (
            "Summarize long text. Use strategy: 'head' (first N chars), 'tail' (last N chars), "
            "'head_tail' (first + last), or 'sentences' (first N sentences)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to summarize."},
                "strategy": {
                    "type": "string",
                    "enum": ["head", "tail", "head_tail", "sentences"],
                    "description": "Summarization strategy.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters for head/tail (default 500).",
                    "default": 500,
                },
                "max_sentences": {
                    "type": "integer",
                    "description": "Max sentences when strategy is 'sentences' (default 5).",
                    "default": 5,
                },
            },
            "required": ["text", "strategy"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        text = (kwargs.get("text") or "").strip()
        strategy = (kwargs.get("strategy") or "head").lower()
        max_chars = max(1, int(kwargs.get("max_chars", 500)))
        max_sentences = max(1, int(kwargs.get("max_sentences", 5)))

        if not text:
            return ToolResult(success=False, output="", error="No text provided.")

        try:
            if strategy == "head":
                out = text[:max_chars]
                if len(text) > max_chars:
                    out += "…"
            elif strategy == "tail":
                out = text[-max_chars:] if len(text) > max_chars else text
                if len(text) > max_chars:
                    out = "…" + out
            elif strategy == "head_tail":
                half = max_chars // 2
                if len(text) <= max_chars:
                    out = text
                else:
                    out = text[:half] + " … " + text[-half:]
            elif strategy == "sentences":
                sentences = self._split_sentences(text)
                out = " ".join(sentences[:max_sentences])
                if len(sentences) > max_sentences:
                    out += "…"
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown strategy: {strategy}. Use head, tail, head_tail, or sentences.",
                )
            return ToolResult(success=True, output=out, metadata={"strategy": strategy})
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        # Simple sentence boundary: . ! ? followed by space or end
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]
