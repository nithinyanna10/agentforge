"""Text utilities: chunking and token estimation (next-level)."""

from __future__ import annotations

import re


def chunk_by_chars(text: str, chunk_size: int, overlap: int = 0) -> list[str]:
    """Split text into chunks of at most chunk_size chars with optional overlap."""
    if chunk_size <= 0:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap if overlap > 0 and end < len(text) else end
    return chunks or [text]


def chunk_by_sentences(text: str, sentences_per_chunk: int) -> list[str]:
    """Split text into chunks of up to N sentences."""
    if sentences_per_chunk <= 0:
        return [text] if text else []
    parts = re.split(r"(?<=[.!?])\s+", text)
    parts = [p.strip() for p in parts if p.strip()]
    return [" ".join(parts[i : i + sentences_per_chunk]) for i in range(0, len(parts), sentences_per_chunk)] or [text]


def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Rough token estimate: ~4 chars per token for English, conservative for code.
    Not accurate for all models; use for truncation hints only.
    """
    if not text:
        return 0
    n = len(text)
    if "gpt-4" in model or "gpt-3" in model:
        return (n // 4) + 1
    return (n // 3) + 1
