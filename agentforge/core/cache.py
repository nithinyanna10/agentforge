"""LLM response cache — in-memory and disk-backed to avoid duplicate API calls."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentforge.llm.base import BaseLLMProvider, LLMResponse, Message
from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CacheKey(BaseModel):
    """Unique key for a cached LLM request."""

    provider: str
    model: str
    messages_hash: str
    tools_hash: str
    temperature: float = 0.7


class CacheEntry(BaseModel):
    """Stored cache value with metadata."""

    key: CacheKey
    response: LLMResponse
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hit_count: int = 0
    ttl_seconds: int = 3600

    def is_expired(self) -> bool:
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


def _hash_messages(messages: list[Message]) -> str:
    parts = []
    for m in messages:
        parts.append(f"{m.role.value}:{m.content or ''}:{m.tool_call_id or ''}")
        if m.tool_calls:
            for tc in m.tool_calls:
                parts.append(f"tc:{tc.id}:{tc.function_name}:{json.dumps(tc.arguments, sort_keys=True)}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _hash_tools(tools: list[dict[str, Any]] | None) -> str:
    if not tools:
        return ""
    return hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest()


def make_cache_key(
    provider_name: str,
    model: str,
    messages: list[Message],
    tools: list[dict[str, Any]] | None,
    temperature: float = 0.7,
) -> CacheKey:
    """Build a cache key from provider, model, messages, and tools."""
    return CacheKey(
        provider=provider_name,
        model=model,
        messages_hash=_hash_messages(messages),
        tools_hash=_hash_tools(tools),
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Base cache
# ---------------------------------------------------------------------------


class BaseCache:
    """Abstract cache backend for LLM responses."""

    async def get(self, key: CacheKey) -> LLMResponse | None:
        """Return cached response if present and not expired."""
        raise NotImplementedError

    async def set(
        self,
        key: CacheKey,
        response: LLMResponse,
        ttl_seconds: int = 3600,
    ) -> None:
        """Store a response under the given key."""
        raise NotImplementedError

    async def invalidate(self, key: CacheKey) -> None:
        """Remove a single entry."""
        raise NotImplementedError

    async def clear(self) -> None:
        """Remove all entries."""
        raise NotImplementedError

    async def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# In-memory LRU cache
# ---------------------------------------------------------------------------


class InMemoryCache(BaseCache):
    """LRU in-memory cache with max size and TTL."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._lock: Any = None

    def _get_lock(self) -> Any:
        import asyncio
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _key_str(self, key: CacheKey) -> str:
        return f"{key.provider}:{key.model}:{key.messages_hash}:{key.tools_hash}:{key.temperature}"

    async def get(self, key: CacheKey) -> LLMResponse | None:
        async with self._get_lock():
            k = self._key_str(key)
            entry = self._store.get(k)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired():
                del self._store[k]
                self._misses += 1
                return None
            entry.hit_count += 1
            self._hits += 1
            self._store.move_to_end(k)
            return entry.response

    async def set(
        self,
        key: CacheKey,
        response: LLMResponse,
        ttl_seconds: int | None = None,
    ) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        async with self._get_lock():
            k = self._key_str(key)
            while len(self._store) >= self._max_size and k not in self._store:
                self._store.popitem(last=False)
            self._store[k] = CacheEntry(key=key, response=response, ttl_seconds=ttl)
            self._store.move_to_end(k)

    async def invalidate(self, key: CacheKey) -> None:
        async with self._get_lock():
            k = self._key_str(key)
            self._store.pop(k, None)

    async def clear(self) -> None:
        async with self._get_lock():
            self._store.clear()
            self._hits = 0
            self._misses = 0

    async def stats(self) -> dict[str, Any]:
        async with self._get_lock():
            total = self._hits + self._misses
            hit_rate = self._hits / total if total else 0.0
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
            }


# ---------------------------------------------------------------------------
# Disk (SQLite) cache
# ---------------------------------------------------------------------------


class DiskCache(BaseCache):
    """SQLite-backed persistent cache with TTL and auto-prune."""

    def __init__(self, db_path: str | Path, default_ttl: int = 3600) -> None:
        self._db_path = Path(db_path)
        self._default_ttl = default_ttl
        self._initialized = False
        self._hits = 0
        self._misses = 0

    async def _ensure_table(self) -> None:
        if self._initialized:
            return
        import aiosqlite
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key_hash TEXT PRIMARY KEY,
                    key_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    hits INTEGER NOT NULL DEFAULT 0,
                    ttl_seconds INTEGER NOT NULL
                )
                """
            )
            await db.commit()
        self._initialized = True

    def _key_hash(self, key: CacheKey) -> str:
        return hashlib.sha256(key.model_dump_json().encode()).hexdigest()

    async def get(self, key: CacheKey) -> LLMResponse | None:
        import aiosqlite
        await self._ensure_table()
        kh = self._key_hash(key)
        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT response_json, created_at, hits, ttl_seconds FROM cache_entries WHERE key_hash = ?",
                (kh,),
            )
            row = await cursor.fetchone()
        if row is None:
            self._misses += 1
            return None
        created = datetime.fromisoformat(row["created_at"])
        ttl = row["ttl_seconds"]
        elapsed = (datetime.now(timezone.utc) - created).total_seconds()
        if elapsed > ttl:
            async with aiosqlite.connect(str(self._db_path)) as db:
                await db.execute("DELETE FROM cache_entries WHERE key_hash = ?", (kh,))
                await db.commit()
            self._misses += 1
            return None
        self._hits += 1
        data = json.loads(row["response_json"])
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute(
                "UPDATE cache_entries SET hits = hits + 1 WHERE key_hash = ?",
                (kh,),
            )
            await db.commit()
        return LLMResponse.model_validate(data)

    async def set(
        self,
        key: CacheKey,
        response: LLMResponse,
        ttl_seconds: int | None = None,
    ) -> None:
        import aiosqlite
        await self._ensure_table()
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        kh = self._key_hash(key)
        key_json = key.model_dump_json()
        response_json = response.model_dump_json()
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (key_hash, key_json, response_json, created_at, hits, ttl_seconds)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (kh, key_json, response_json, now, ttl),
            )
            await db.commit()
        logger.debug("DiskCache set key %s", kh[:16])

    async def invalidate(self, key: CacheKey) -> None:
        import aiosqlite
        await self._ensure_table()
        kh = self._key_hash(key)
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute("DELETE FROM cache_entries WHERE key_hash = ?", (kh,))
            await db.commit()

    async def clear(self) -> None:
        import aiosqlite
        await self._ensure_table()
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute("DELETE FROM cache_entries")
            await db.commit()
        self._hits = 0
        self._misses = 0
        logger.info("DiskCache cleared")

    async def stats(self) -> dict[str, Any]:
        import aiosqlite
        await self._ensure_table()
        async with aiosqlite.connect(str(self._db_path)) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM cache_entries")
            row = await cursor.fetchone()
        size = row[0] if row else 0
        total = self._hits + self._misses
        hit_rate = self._hits / total if total else 0.0
        return {
            "size": size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
        }


# ---------------------------------------------------------------------------
# Cache middleware (wraps provider)
# ---------------------------------------------------------------------------


class CacheMiddleware(BaseLLMProvider):
    """Wraps a BaseLLMProvider and caches complete() responses."""

    def __init__(
        self,
        provider: BaseLLMProvider,
        cache: BaseCache,
        provider_name: str = "unknown",
    ) -> None:
        super().__init__(
            provider.model,
            temperature=getattr(provider, "default_temperature", 0.7),
            max_tokens=getattr(provider, "default_max_tokens", 4096),
        )
        self._provider = provider
        self._cache = cache
        self._provider_name = provider_name

    @property
    def model(self) -> str:
        return self._provider.model

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        key = make_cache_key(
            self._provider_name,
            self._provider.model,
            messages,
            tools,
            temperature or self.default_temperature,
        )
        cached = await self._cache.get(key)
        if cached is not None:
            logger.debug("Cache hit for %s", key.model)
            return cached
        response = await self._provider.complete(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        await self._cache.set(key, response)
        return response

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        return self._provider.stream(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def format_tools(self, tools: Any) -> list[dict[str, Any]]:
        return self._provider.format_tools(tools)
