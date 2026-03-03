"""Tests for agentforge.core.memory memory stores."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentforge.core.memory import (
    CompositeMemory,
    ConversationMemory,
    MemoryEntry,
    VectorMemory,
)


# ---------------------------------------------------------------------------
# ConversationMemory (uses aiosqlite — a real temp DB via tmp_path)
# ---------------------------------------------------------------------------

async def test_conversation_memory_add_and_get_recent(tmp_path):
    db = tmp_path / "test.db"
    mem = ConversationMemory(db_path=db)

    await mem.add("first message", {"role": "user"})
    await mem.add("second message", {"role": "assistant"})
    await mem.add("third message", {"role": "user"})

    recent = await mem.get_recent(limit=2)

    assert len(recent) == 2
    assert recent[0].content == "second message"
    assert recent[1].content == "third message"


async def test_conversation_memory_search(tmp_path):
    db = tmp_path / "search.db"
    mem = ConversationMemory(db_path=db)

    await mem.add("The weather is sunny today")
    await mem.add("I like programming in Python")
    await mem.add("The weather forecast says rain tomorrow")

    results = await mem.search("weather", top_k=5)

    assert len(results) == 2
    assert all("weather" in e.content.lower() for e in results)


async def test_conversation_memory_clear(tmp_path):
    db = tmp_path / "clear.db"
    mem = ConversationMemory(db_path=db)

    await mem.add("entry one")
    await mem.add("entry two")
    await mem.clear()

    recent = await mem.get_recent(limit=10)
    assert len(recent) == 0


# ---------------------------------------------------------------------------
# VectorMemory (chromadb mocked out)
# ---------------------------------------------------------------------------

async def test_vector_memory_add_and_search():
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["Agent orchestration is key"]],
        "metadatas": [[{"timestamp": "2026-01-01T00:00:00+00:00"}]],
        "distances": [[0.15]],
    }

    mem = VectorMemory(collection_name="test_col")
    mem._collection = mock_collection

    await mem.add("Agent orchestration is key", {"topic": "ai"})
    mock_collection.add.assert_called_once()

    results = await mem.search("orchestration", top_k=3)

    assert len(results) == 1
    assert results[0].content == "Agent orchestration is key"
    assert results[0].score == pytest.approx(0.85)


async def test_vector_memory_clear():
    mock_collection = MagicMock()
    mock_collection.get.return_value = {"ids": ["id1", "id2"]}

    mem = VectorMemory()
    mem._collection = mock_collection

    await mem.clear()
    mock_collection.delete.assert_called_once_with(ids=["id1", "id2"])


# ---------------------------------------------------------------------------
# CompositeMemory
# ---------------------------------------------------------------------------

async def test_composite_memory_writes_to_both():
    conv = AsyncMock(spec=ConversationMemory)
    vec = AsyncMock(spec=VectorMemory)

    composite = CompositeMemory(conversation=conv, vector=vec)
    await composite.add("important fact", {"source": "test"})

    conv.add.assert_awaited_once_with("important fact", {"source": "test"})
    vec.add.assert_awaited_once_with("important fact", {"source": "test"})


async def test_composite_memory_search_merges():
    conv = AsyncMock(spec=ConversationMemory)
    vec = AsyncMock(spec=VectorMemory)

    conv.search.return_value = [
        MemoryEntry(content="from conversation"),
    ]
    vec.search.return_value = [
        MemoryEntry(content="from vector", score=0.9),
    ]

    composite = CompositeMemory(conversation=conv, vector=vec)
    results = await composite.search("query", top_k=5)

    assert len(results) == 2
    contents = {e.content for e in results}
    assert "from conversation" in contents
    assert "from vector" in contents


async def test_composite_memory_clear():
    conv = AsyncMock(spec=ConversationMemory)
    vec = AsyncMock(spec=VectorMemory)

    composite = CompositeMemory(conversation=conv, vector=vec)
    await composite.clear()

    conv.clear.assert_awaited_once()
    vec.clear.assert_awaited_once()
