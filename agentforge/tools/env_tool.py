"""Environment tool — read (and optionally list) environment variables safely."""

from __future__ import annotations

import os
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class EnvTool(Tool):
    """Read environment variables. Only non-sensitive keys are listable; specific key read is allowed."""

    # Keys that are never exposed in list_env (sensitive or noisy)
    MASKED_PREFIXES = ("SECRET", "KEY", "PASSWORD", "TOKEN", "CREDENTIAL", "PRIVATE", "API_KEY")

    @property
    def name(self) -> str:
        return "env"

    @property
    def description(self) -> str:
        return (
            "Read an environment variable by name, or list safe env keys (no secrets). "
            "Use get to read a specific key; use list to see available key names."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "list"],
                    "description": "Get one variable by name, or list safe variable names.",
                },
                "key": {"type": "string", "description": "Variable name (for action get)."},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "").strip().lower()
        key = (kwargs.get("key") or "").strip()

        if action == "get":
            if not key:
                return ToolResult(success=False, output="", error="Key is required for action 'get'.")
            if self._is_masked(key):
                return ToolResult(success=False, output="", error="Access to this key is not allowed.")
            value = os.environ.get(key)
            if value is None:
                return ToolResult(success=True, output="(not set)", metadata={"key": key})
            return ToolResult(success=True, output=value, metadata={"key": key})
        elif action == "list":
            safe = [k for k in sorted(os.environ) if not self._is_masked(k)]
            out = "\n".join(safe) if safe else "(no safe keys)"
            return ToolResult(success=True, output=out, metadata={"count": len(safe)})
        else:
            return ToolResult(success=False, output="", error="Action must be 'get' or 'list'.")

    @classmethod
    def _is_masked(cls, key: str) -> bool:
        up = key.upper()
        return any(up.startswith(p) for p in cls.MASKED_PREFIXES)
