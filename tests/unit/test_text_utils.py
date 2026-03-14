"""Tests for text_utils."""

from __future__ import annotations

import pytest
from agentforge.utils.text_utils import chunk_by_chars, chunk_by_sentences, estimate_tokens


def test_chunk_by_chars() -> None:
    text = "abcdefghij"
    assert chunk_by_chars(text, 3) == ["abc", "def", "ghi", "j"]
    chunks_overlap = chunk_by_chars(text, 3, overlap=1)
    assert len(chunks_overlap) >= 3
    assert "".join(c for c in chunks_overlap if len(c) == 3) == "abcdefghi" or chunks_overlap[0] == "abc"


def test_chunk_by_sentences() -> None:
    text = "One. Two. Three. Four."
    assert len(chunk_by_sentences(text, 2)) == 2
    assert chunk_by_sentences("Single.", 5) == ["Single."]


def test_estimate_tokens() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello") >= 1
    assert estimate_tokens("x" * 40) >= 10
