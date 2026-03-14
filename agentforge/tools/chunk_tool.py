"""Chunk tool — split text into chunks by size or sentences (next-level)."""

from __future__ import annotations

import re
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class ChunkTool(Tool):
    """Split long text into chunks by max characters or by sentence count."""

    @property
    def name(self) -> str:
        return "chunk_text"

    @property
    def description(self) -> str:
        return (
            "Split text into chunks. Strategy: by_chars (split every N chars) or "
            "by_sentences (split every N sentences, keeping sentence boundaries)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to chunk."},
                "strategy": {
                    "type": "string",
                    "enum": ["by_chars", "by_sentences"],
                    "description": "Chunking strategy.",
                },
                "chunk_size": {
                    "type": "integer",
                    "description": "Max chars per chunk (by_chars) or sentences per chunk (by_sentences).",
                    "default": 500,
                },
                "overlap": {
                    "type": "integer",
                    "description": "Overlap in chars between consecutive chunks (by_chars only).",
                    "default": 0,
                },
            },
            "required": ["text", "strategy"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        text = (kwargs.get("text") or "").strip()
        strategy = (kwargs.get("strategy") or "by_chars").strip().lower()
        chunk_size = max(1, int(kwargs.get("chunk_size", 500)))
        overlap = max(0, int(kwargs.get("overlap", 0)))

        if not text:
            return ToolResult(success=False, output="", error="No text provided.")

        try:
            if strategy == "by_chars":
                chunks = self._chunk_by_chars(text, chunk_size, overlap)
            elif strategy == "by_sentences":
                chunks = self._chunk_by_sentences(text, chunk_size)
            else:
                return ToolResult(success=False, output="", error=f"Unknown strategy: {strategy}")
            out = "\n\n---CHUNK---\n\n".join(chunks)
            return ToolResult(
                success=True,
                output=out,
                metadata={"strategy": strategy, "chunk_count": len(chunks), "chunk_size": chunk_size},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    @staticmethod
    def _chunk_by_chars(text: str, size: int, overlap: int) -> list[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunks.append(text[start:end])
            start = end - overlap if overlap > 0 and end < len(text) else end
        return chunks if chunks else [text]

    @staticmethod
    def _chunk_by_sentences(text: str, sentences_per_chunk: int) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text)
        parts = [p.strip() for p in parts if p.strip()]
        chunks = []
        for i in range(0, len(parts), sentences_per_chunk):
            chunk = " ".join(parts[i : i + sentences_per_chunk])
            chunks.append(chunk)
        return chunks if chunks else [text]
