"""Safe Python code execution tool using subprocess isolation."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from agentforge.tools.base import Tool, ToolResult

_MAX_OUTPUT_BYTES = 64 * 1024  # 64 KiB cap on captured output


class CodeExecutorTool(Tool):
    """Execute Python code in an isolated subprocess with a timeout."""

    @property
    def name(self) -> str:
        return "code_executor"

    @property
    def description(self) -> str:
        return (
            "Execute a Python code snippet in a sandboxed subprocess "
            "and return stdout/stderr."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python source code to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds.",
                    "default": 30,
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        code: str = kwargs["code"]
        timeout: int = kwargs.get("timeout", 30)

        tmp = Path(tempfile.mkstemp(suffix=".py", prefix="agentforge_")[1])
        try:
            tmp.write_text(code, encoding="utf-8")
            return await self._run(tmp, timeout)
        finally:
            tmp.unlink(missing_ok=True)

    async def _run(self, script: Path, timeout: int) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                "-u",
                str(script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={"PATH": "/usr/bin:/usr/local/bin"},
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()  # type: ignore[union-attr]
            await proc.wait()  # type: ignore[union-attr]
            return ToolResult(
                success=False,
                output="",
                error=f"Execution timed out after {timeout}s",
                metadata={"timeout": timeout},
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                output="",
                error="python3 interpreter not found on PATH",
            )

        stdout = stdout_bytes[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        stderr = stderr_bytes[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        exit_code = proc.returncode or 0

        if exit_code != 0:
            return ToolResult(
                success=False,
                output=stdout,
                error=stderr or f"Process exited with code {exit_code}",
                metadata={"exit_code": exit_code},
            )

        return ToolResult(
            success=True,
            output=stdout,
            error=stderr if stderr else None,
            metadata={"exit_code": exit_code},
        )
