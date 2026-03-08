"""Persistent run history — store and query agent run results."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


class StoredRun(BaseModel):
    """A single run record for persistence."""

    run_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    agent_name: str = ""
    task: str = ""
    answer: str = ""
    tool_calls_json: str = "[]"
    thinking_steps_json: str = "[]"
    duration_seconds: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata_json: str = "{}"

    def to_agent_result_attrs(self) -> dict[str, Any]:
        """Return dict suitable for reconstructing AgentResult-like view."""
        return {
            "agent_name": self.agent_name,
            "task": self.task,
            "answer": self.answer,
            "tool_calls": json.loads(self.tool_calls_json),
            "thinking_steps": json.loads(self.thinking_steps_json),
            "duration_seconds": self.duration_seconds,
            "metadata": json.loads(self.metadata_json),
        }


class RunStore:
    """SQLite-backed store for agent run history."""

    def __init__(self, db_path: str | Path = "agentforge_runs.db") -> None:
        self._db_path = Path(db_path)
        self._initialized = False

    async def _ensure_table(self) -> None:
        if self._initialized:
            return
        import aiosqlite

        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    task TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    tool_calls_json TEXT NOT NULL DEFAULT '[]',
                    thinking_steps_json TEXT NOT NULL DEFAULT '[]',
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_agent ON runs(agent_name)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at)"
            )
            await db.commit()
        self._initialized = True

    async def save(
        self,
        agent_name: str,
        task: str,
        answer: str,
        tool_calls: list[Any],
        thinking_steps: list[str],
        duration_seconds: float,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> str:
        """Persist a run and return its run_id."""
        import aiosqlite

        await self._ensure_table()
        rid = run_id or uuid4().hex[:16]
        now = datetime.now(timezone.utc).isoformat()
        tool_json = json.dumps([c.model_dump() if hasattr(c, "model_dump") else c for c in tool_calls])
        meta_json = json.dumps(metadata or {})

        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute(
                """INSERT INTO runs (
                    run_id, agent_name, task, answer, tool_calls_json,
                    thinking_steps_json, duration_seconds, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rid,
                    agent_name,
                    task,
                    answer,
                    tool_json,
                    json.dumps(thinking_steps),
                    duration_seconds,
                    now,
                    meta_json,
                ),
            )
            await db.commit()
        logger.debug("RunStore saved run %s", rid)
        return rid

    async def get(self, run_id: str) -> StoredRun | None:
        """Load a single run by id."""
        import aiosqlite

        await self._ensure_table()
        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return StoredRun(
            run_id=row["run_id"],
            agent_name=row["agent_name"],
            task=row["task"],
            answer=row["answer"],
            tool_calls_json=row["tool_calls_json"],
            thinking_steps_json=row["thinking_steps_json"],
            duration_seconds=row["duration_seconds"],
            created_at=row["created_at"],
            metadata_json=row["metadata_json"],
        )

    async def list_recent(
        self,
        limit: int = 50,
        agent_name: str | None = None,
    ) -> list[StoredRun]:
        """List most recent runs, optionally filtered by agent_name."""
        import aiosqlite

        await self._ensure_table()
        if agent_name:
            sql = "SELECT * FROM runs WHERE agent_name = ? ORDER BY created_at DESC LIMIT ?"
            params = (agent_name, limit)
        else:
            sql = "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?"
            params = (limit,)
        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        return [
            StoredRun(
                run_id=r["run_id"],
                agent_name=r["agent_name"],
                task=r["task"],
                answer=r["answer"],
                tool_calls_json=r["tool_calls_json"],
                thinking_steps_json=r["thinking_steps_json"],
                duration_seconds=r["duration_seconds"],
                created_at=r["created_at"],
                metadata_json=r["metadata_json"],
            )
            for r in rows
        ]

    async def clear(self) -> None:
        """Delete all stored runs."""
        import aiosqlite

        await self._ensure_table()
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute("DELETE FROM runs")
            await db.commit()
        logger.info("RunStore cleared")
