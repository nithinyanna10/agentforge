"""Tests for DiffTool and ChunkTool."""

from __future__ import annotations

import pytest
from agentforge.tools.diff_tool import DiffTool
from agentforge.tools.chunk_tool import ChunkTool


@pytest.fixture
def diff_tool() -> DiffTool:
    return DiffTool()


@pytest.fixture
def chunk_tool() -> ChunkTool:
    return ChunkTool()


class TestDiffTool:
    @pytest.mark.asyncio
    async def test_diff_same(self, diff_tool: DiffTool) -> None:
        t = "hello"
        result = await diff_tool.execute(old_text=t, new_text=t, output="diff")
        assert result.success is True
        assert "no diff" in result.output.lower() or result.output.strip() == ""

    @pytest.mark.asyncio
    async def test_diff_summary(self, diff_tool: DiffTool) -> None:
        result = await diff_tool.execute(
            old_text="a\nb\nc",
            new_text="a\nb\nc\nd",
            output="summary",
        )
        assert result.success is True
        assert "added" in result.output.lower() or "1" in result.output
        assert result.metadata.get("additions") is not None

    @pytest.mark.asyncio
    async def test_diff_unified(self, diff_tool: DiffTool) -> None:
        result = await diff_tool.execute(
            old_text="line1",
            new_text="line2",
            output="diff",
        )
        assert result.success is True
        assert "line1" in result.output or "line2" in result.output or "---" in result.output


class TestChunkTool:
    @pytest.mark.asyncio
    async def test_chunk_by_chars(self, chunk_tool: ChunkTool) -> None:
        text = "a" * 1000
        result = await chunk_tool.execute(text=text, strategy="by_chars", chunk_size=300)
        assert result.success is True
        assert result.metadata.get("chunk_count", 0) >= 3
        assert "---CHUNK---" in result.output

    @pytest.mark.asyncio
    async def test_chunk_by_sentences(self, chunk_tool: ChunkTool) -> None:
        text = "First. Second. Third. Fourth. Fifth."
        result = await chunk_tool.execute(text=text, strategy="by_sentences", chunk_size=2)
        assert result.success is True
        assert result.metadata.get("chunk_count", 0) >= 2

    @pytest.mark.asyncio
    async def test_chunk_empty(self, chunk_tool: ChunkTool) -> None:
        result = await chunk_tool.execute(text="", strategy="by_chars")
        assert result.success is False
