"""Memory subsystem: conversation history, vector search, and composite stores."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------

class MemoryEntry(BaseModel):
    """A single memory record."""

    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    score: float | None = None  # relevance score when returned from search


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class MemoryStore(ABC):
    """Interface that every memory backend must implement."""

    @abstractmethod
    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Persist a new memory entry."""
        ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """Return the *top_k* most relevant entries for *query*."""
        ...

    @abstractmethod
    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Return the most recent entries in chronological order."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Delete all stored memories."""
        ...


# ---------------------------------------------------------------------------
# Conversation memory backed by SQLite (aiosqlite)
# ---------------------------------------------------------------------------

class ConversationMemory(MemoryStore):
    """Stores chat-style history in a local SQLite database via ``aiosqlite``.

    The database and table are created lazily on first write.
    """

    def __init__(self, db_path: str | Path = "memory.db") -> None:
        self._db_path = str(db_path)
        self._initialised = False

    async def _ensure_table(self) -> None:
        if self._initialised:
            return
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    content   TEXT    NOT NULL,
                    metadata  TEXT    NOT NULL DEFAULT '{}',
                    timestamp TEXT    NOT NULL
                )
                """
            )
            await db.commit()
        self._initialised = True

    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        import aiosqlite

        await self._ensure_table()
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO memories (content, metadata, timestamp) VALUES (?, ?, ?)",
                (content, json.dumps(metadata or {}), now),
            )
            await db.commit()
        logger.debug("ConversationMemory | stored %d chars", len(content))

    async def search(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """Naive substring search — suitable for small histories."""
        import aiosqlite

        await self._ensure_table()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT content, metadata, timestamp FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", top_k),
            )
            rows = await cursor.fetchall()
        return [
            MemoryEntry(
                content=row["content"],
                metadata=json.loads(row["metadata"]),
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
            for row in rows
        ]

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        import aiosqlite

        await self._ensure_table()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT content, metadata, timestamp FROM memories ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [
            MemoryEntry(
                content=row["content"],
                metadata=json.loads(row["metadata"]),
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
            for row in reversed(rows)
        ]

    async def clear(self) -> None:
        import aiosqlite

        await self._ensure_table()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM memories")
            await db.commit()
        logger.info("ConversationMemory | cleared")


# ---------------------------------------------------------------------------
# Vector memory backed by ChromaDB
# ---------------------------------------------------------------------------

class VectorMemory(MemoryStore):
    """Semantic search memory using ChromaDB embeddings.

    ChromaDB is imported lazily so the rest of AgentForge works without it
    if you only need conversation memory.
    """

    def __init__(
        self,
        collection_name: str = "agentforge_memory",
        persist_directory: str | None = None,
    ) -> None:
        self._collection_name = collection_name
        self._persist_directory = persist_directory
        self._collection: Any = None

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection

        import chromadb

        if self._persist_directory:
            client = chromadb.PersistentClient(path=self._persist_directory)
        else:
            client = chromadb.Client()
        self._collection = client.get_or_create_collection(self._collection_name)
        return self._collection

    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        import uuid as _uuid

        collection = self._get_collection()
        doc_id = _uuid.uuid4().hex[:16]
        meta = {**(metadata or {}), "timestamp": datetime.now(timezone.utc).isoformat()}
        collection.add(documents=[content], ids=[doc_id], metadatas=[meta])
        logger.debug("VectorMemory | stored doc %s", doc_id)

    async def search(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        collection = self._get_collection()
        results = collection.query(query_texts=[query], n_results=top_k)
        entries: list[MemoryEntry] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            ts_str = meta.pop("timestamp", None)
            ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
            entries.append(MemoryEntry(content=doc, metadata=meta, timestamp=ts, score=1.0 - dist))
        return entries

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        collection = self._get_collection()
        all_docs = collection.get(limit=limit)
        entries: list[MemoryEntry] = []
        for doc, meta in zip(all_docs["documents"], all_docs["metadatas"]):
            ts_str = meta.pop("timestamp", None)
            ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
            entries.append(MemoryEntry(content=doc, metadata=meta, timestamp=ts))
        return entries

    async def clear(self) -> None:
        collection = self._get_collection()
        ids = collection.get()["ids"]
        if ids:
            collection.delete(ids=ids)
        logger.info("VectorMemory | cleared collection %s", self._collection_name)


# ---------------------------------------------------------------------------
# Composite memory (conversation + vector)
# ---------------------------------------------------------------------------

class CompositeMemory(MemoryStore):
    """Combines a ``ConversationMemory`` and a ``VectorMemory``.

    Writes go to both stores. Reads merge results, preferring semantic
    relevance from the vector store while retaining chronological context
    from conversation memory.
    """

    def __init__(
        self,
        conversation: ConversationMemory | None = None,
        vector: VectorMemory | None = None,
    ) -> None:
        self.conversation = conversation or ConversationMemory()
        self.vector = vector or VectorMemory()

    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        await self.conversation.add(content, metadata)
        await self.vector.add(content, metadata)

    async def search(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        conv_results = await self.conversation.search(query, top_k)
        vec_results = await self.vector.search(query, top_k)

        seen: set[str] = set()
        merged: list[MemoryEntry] = []
        for entry in vec_results + conv_results:
            key = entry.content[:128]
            if key not in seen:
                seen.add(key)
                merged.append(entry)
        return merged[:top_k]

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        return await self.conversation.get_recent(limit)

    async def clear(self) -> None:
        await self.conversation.clear()
        await self.vector.clear()
