"""SQLite read-only query tool with sandboxed database path."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agentforge.tools.base import Tool, ToolResult

# Allow only SELECT; strip comments and normalize whitespace
_SELECT_ONLY = re.compile(r"^\s*SELECT\s+", re.IGNORECASE | re.DOTALL)
_FORBIDDEN = re.compile(
    r"(\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|ATTACH|PRAGMA\s+write)\b)",
    re.IGNORECASE,
)


class SqlQueryTool(Tool):
    """Run read-only SQL (SELECT) against a SQLite database file."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path).resolve()
        if not self._db_path.is_file():
            raise ValueError(f"Database file does not exist: {self._db_path}")

    @property
    def name(self) -> str:
        return "sql_query"

    @property
    def description(self) -> str:
        return (
            "Execute a read-only SQL SELECT query against a SQLite database. "
            "Only SELECT statements are allowed. Use for querying data."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A single SQL SELECT query (no semicolon required).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return (default 100).",
                    "default": 100,
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = (kwargs.get("query") or "").strip()
        limit = min(max(int(kwargs.get("limit", 100)), 1), 1000)

        if not query:
            return ToolResult(success=False, output="", error="'query' is required")

        if not _SELECT_ONLY.match(query):
            return ToolResult(
                success=False,
                output="",
                error="Only SELECT queries are allowed. Other statements are disabled.",
            )
        if _FORBIDDEN.search(query):
            return ToolResult(
                success=False,
                output="",
                error="Query contains forbidden keywords (e.g. INSERT, UPDATE, DELETE).",
            )

        try:
            import aiosqlite

            async with aiosqlite.connect(str(self._db_path)) as conn:
                conn.row_factory = aiosqlite.Row
                # Enforce limit if not present
                if " limit " not in query.lower():
                    query = query.rstrip(";").strip() + f" LIMIT {limit}"
                cursor = await conn.execute(query)
                rows = await cursor.fetchall()
                columns = [d[0] for d in cursor.description] if cursor.description else []
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

        if not columns:
            return ToolResult(
                success=True,
                output="(no columns)",
                metadata={"row_count": 0},
            )

        lines = ["\t".join(columns)]
        for row in rows:
            lines.append("\t".join(str(row[c]) for c in columns))
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"row_count": len(rows), "columns": columns},
        )
