"""File operations tool with configurable base-directory sandboxing."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

from agentforge.tools.base import Tool, ToolResult

_DEFAULT_READ_LIMIT = 1024 * 1024  # 1 MiB


class FileOpsTool(Tool):
    """Perform file-system operations restricted to a configurable base directory."""

    def __init__(self, base_directory: str | Path) -> None:
        self._base = Path(base_directory).resolve()
        if not self._base.is_dir():
            raise ValueError(f"Base directory does not exist: {self._base}")

    @property
    def name(self) -> str:
        return "file_ops"

    @property
    def description(self) -> str:
        return (
            "Read, write, list, and search files within a sandboxed directory. "
            f"Base directory: {self._base}"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read_file", "write_file", "list_directory", "search_files"],
                    "description": "The file operation to perform.",
                },
                "path": {
                    "type": "string",
                    "description": "Relative path (from the base directory) for the operation.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (required for write_file).",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern for search_files (e.g. '*.py').",
                },
            },
            "required": ["operation"],
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(self, **kwargs: Any) -> ToolResult:
        operation: str = kwargs["operation"]
        dispatch = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "list_directory": self._list_directory,
            "search_files": self._search_files,
        }
        handler = dispatch.get(operation)
        if handler is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown operation: {operation}",
            )
        return await handler(**kwargs)

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def _read_file(self, **kwargs: Any) -> ToolResult:
        resolved = self._safe_resolve(kwargs.get("path", ""))
        if resolved is None:
            return self._path_error()
        if not resolved.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {resolved.name}")
        try:
            content = resolved.read_text(encoding="utf-8")[:_DEFAULT_READ_LIMIT]
            return ToolResult(
                success=True,
                output=content,
                metadata={"path": str(resolved.relative_to(self._base)), "bytes": len(content)},
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    async def _write_file(self, **kwargs: Any) -> ToolResult:
        resolved = self._safe_resolve(kwargs.get("path", ""))
        if resolved is None:
            return self._path_error()
        content: str | None = kwargs.get("content")
        if content is None:
            return ToolResult(success=False, output="", error="'content' is required for write_file")
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Wrote {len(content)} bytes to {resolved.relative_to(self._base)}",
                metadata={"path": str(resolved.relative_to(self._base)), "bytes": len(content)},
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    async def _list_directory(self, **kwargs: Any) -> ToolResult:
        resolved = self._safe_resolve(kwargs.get("path", ""))
        if resolved is None:
            return self._path_error()
        if not resolved.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {resolved.name}")
        try:
            entries: list[str] = []
            for entry in sorted(resolved.iterdir()):
                suffix = "/" if entry.is_dir() else ""
                entries.append(f"{entry.name}{suffix}")
            return ToolResult(
                success=True,
                output="\n".join(entries) if entries else "(empty directory)",
                metadata={"path": str(resolved.relative_to(self._base)), "count": len(entries)},
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    async def _search_files(self, **kwargs: Any) -> ToolResult:
        pattern: str = kwargs.get("pattern", "*")
        resolved = self._safe_resolve(kwargs.get("path", ""))
        if resolved is None:
            return self._path_error()
        if not resolved.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {resolved.name}")
        try:
            matches: list[str] = []
            for root, _dirs, files in os.walk(resolved):
                for fname in files:
                    if fnmatch.fnmatch(fname, pattern):
                        full = Path(root) / fname
                        matches.append(str(full.relative_to(self._base)))
            matches.sort()
            return ToolResult(
                success=True,
                output="\n".join(matches) if matches else "No matches found.",
                metadata={"pattern": pattern, "count": len(matches)},
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

    # ------------------------------------------------------------------
    # Safety helpers
    # ------------------------------------------------------------------

    def _safe_resolve(self, rel_path: str) -> Path | None:
        """Resolve *rel_path* against the base directory, rejecting traversal."""
        try:
            target = (self._base / rel_path).resolve()
        except (ValueError, OSError):
            return None
        if not str(target).startswith(str(self._base)):
            return None
        return target

    @staticmethod
    def _path_error() -> ToolResult:
        return ToolResult(
            success=False,
            output="",
            error="Path resolves outside the allowed base directory.",
        )
