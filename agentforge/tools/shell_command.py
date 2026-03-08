"""Safe shell command execution with allowlist and timeout."""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from agentforge.tools.base import Tool, ToolResult

# Commands allowed by default (no path traversal, no shell metacharacters in single command)
_DEFAULT_ALLOWLIST = frozenset({
    "cat", "head", "tail", "wc", "grep", "find", "ls", "pwd", "date",
    "echo", "env", "whoami", "uname", "df", "du", "which", "type",
    "python", "python3", "pip", "pip3", "node", "npm", "git", "curl",
})


class ShellCommandTool(Tool):
    """Execute a single shell command from an allowlist with a timeout."""

    def __init__(
        self,
        allowlist: set[str] | None = None,
        timeout_seconds: int = 30,
        working_dir: str | None = None,
    ) -> None:
        self._allowlist = allowlist or set(_DEFAULT_ALLOWLIST)
        self._timeout = max(1, min(timeout_seconds, 300))
        self._cwd = working_dir

    @property
    def name(self) -> str:
        return "shell_command"

    @property
    def description(self) -> str:
        return (
            "Run a single allowed shell command (e.g. ls, cat, grep, date). "
            f"Allowed commands: {', '.join(sorted(self._allowlist)[:15])}{'…' if len(self._allowlist) > 15 else ''}. "
            f"Timeout: {self._timeout}s."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to run (e.g. 'ls -la', 'date', 'cat path/to/file'). Only one command; no pipes or redirects.",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        raw = (kwargs.get("command") or "").strip()
        if not raw:
            return ToolResult(success=False, output="", error="'command' is required")

        parts = shlex.split(raw)
        if not parts:
            return ToolResult(success=False, output="", error="Empty command after parsing")

        cmd_name = parts[0].split("/")[-1].lower()
        if cmd_name not in self._allowlist:
            return ToolResult(
                success=False,
                output="",
                error=f"Command '{cmd_name}' is not in the allowlist. Allowed: {sorted(self._allowlist)}",
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                *parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(self._timeout),
            )
            stdout = (stdout_bytes or b"").decode("utf-8", errors="replace")
            stderr = (stderr_bytes or b"").decode("utf-8", errors="replace")
            out = stdout.strip() or stderr.strip() or "(no output)"
            return ToolResult(
                success=proc.returncode == 0,
                output=out[:32_000],
                error=None if proc.returncode == 0 else stderr[:2000] or f"Exit code {proc.returncode}",
                metadata={"returncode": proc.returncode},
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {self._timeout}s",
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))
